"""章节分析：为每章生成摘要、出场人物、功能标签等结构化数据。

工作流程：
1. 读取 chapter_index.yaml（章节索引）和 source.txt（原文）
2. 调用 LLM 分析每章内容，生成：
   - summary：50-100 字摘要
   - characters_appear：出场人物列表
   - chapter_functions：章节功能标签
   - tension_level：紧张程度（1-5）
3. 结果写入 chapters/{章节号}.yaml（每章独立文件）
4. 完成后合并为 chapters.yaml（完整快照）

特性：
- 断点续传：已分析的章节自动跳过，从中断处继续
- 批量处理：可一次分析多章，减少 API 调用次数
- Token 截断：每章内容限制在 1800 tokens 内，避免超出 API 上限
"""
import sys
import yaml
import time
from pathlib import Path

from novel_material.infra.config import NOVELS_DIR, update_meta_status
from novel_material.infra.llm import load_config, call_llm, truncate_to_tokens
from novel_material.validation.quality import run_quality_check
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()

# 每章最大 Token 数（保留章节核心内容，避免超出 API 限制）
_MAX_CHAPTER_TOKENS = 1800

_SYSTEM_PROMPT = """你是专业的小说分析助手，负责对每章内容生成摘要和分析。
要求：
1. 摘要 50-100 字，包含关键事件、情感基调、人物互动
2. chapter_functions 从标签字典的章节功能标签中选取
3. 准确识别出场人物（仅写名字，不写描述）
4. tension_level 1-5，根据紧张程度评估"""

# LLM 返回格式的示例（单章）
_CHAPTER_JSON_SCHEMA = """{
  "chapter": 1,
  "summary": "章节摘要，50-100字",
  "word_count": 3000,
  "characters_appear": ["人物名1", "人物名2"],
  "chapter_functions": ["日常", "战斗"],
  "tension_level": 3,
  "pacing": "快",
  "setting": ["室内", "学校"],
  "key_plot_point": ""
}"""

# LLM 返回格式的示例（批量）
_BATCH_JSON_SCHEMA = """{
  "chapters": [
    {"chapter": 1, "summary": "第一章摘要", "word_count": 3000, "characters_appear": ["人物名"], "chapter_functions": ["标签"], "tension_level": 3, "pacing": "快", "setting": ["场景"], "key_plot_point": ""},
    {"chapter": 2, "summary": "第二章摘要", "word_count": 2500, "characters_appear": ["人物名"], "chapter_functions": ["标签"], "tension_level": 2, "pacing": "慢", "setting": ["场景"], "key_plot_point": ""}
  ]
}"""


def analyze_chapter(content: str, chapter_info: dict, config: dict) -> dict:
    """分析单个章节，返回结构化数据。

    参数：
        content：章节原文
        chapter_info：章节信息（章节号、标题）
        config：LLM 配置

    返回：
        dict：包含 summary、characters_appear、tension_level 等字段
    """
    model = config["llm"]["model"]
    # 截断过长的章节内容
    truncated = truncate_to_tokens(content, _MAX_CHAPTER_TOKENS, model=model)

    user_prompt = f"""请分析以下章节：

章节号：{chapter_info.get('chapter', 'N/A')}
标题：{chapter_info.get('title', 'N/A')}

内容：
{truncated}

请返回 JSON 格式：
{_CHAPTER_JSON_SCHEMA}"""

    timeout = config["llm"].get("analyze_timeout", 300)
    return call_llm(_SYSTEM_PROMPT, user_prompt, config, timeout_override=timeout)


def analyze_chapters_batch(
    batch_info: list[dict],
    lines: list[str],
    config: dict,
) -> dict[int, dict]:
    """批量分析多个章节，一次 API 调用返回所有结果。

    相比逐章分析，批量处理可以：
    - 减少 API 调用次数（一次调用分析多章）
    - 缩短总处理时间（省去批次间隔等待）

    参数：
        batch_info：要分析的章节信息列表
        lines：原文所有行
        config：LLM 配置

    返回：
        dict：{章节号: 分析结果}，只包含 LLM 成功返回的章节
        缺失的章节需要用 analyze_chapter 单章处理
    """
    model = config["llm"]["model"]
    n = len(batch_info)

    # 构建每章内容
    blocks = []
    for ch_info in batch_info:
        text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])
        truncated = truncate_to_tokens(text, _MAX_CHAPTER_TOKENS, model=model)
        blocks.append(
            f"【第{ch_info['chapter']}章《{ch_info['title']}》》\n{truncated}"
        )

    combined = ("\n\n" + "=" * 30 + "\n\n").join(blocks)

    system_prompt = (
        _SYSTEM_PROMPT
        + f"\n\n本次批量分析 {n} 章，返回 JSON 对象必须包含 chapters 数组，"
        f"每个元素对应一章，顺序与输入一致。"
    )

    user_prompt = f"""请批量分析以下 {n} 章内容：

{combined}

返回 JSON（chapters 数组长度必须等于 {n}）：
{_BATCH_JSON_SCHEMA}

重要：每个元素的 chapter 字段必须是整数，与输入章节号一致。"""

    result = call_llm(
        system_prompt,
        user_prompt,
        config,
        max_tokens_override=n * 450,
        timeout_override=config["llm"].get("analyze_timeout"),
    )

    # 解析返回结果
    chapters_list = result.get("chapters", [])
    if not chapters_list:
        logger.warning(f"批量返回无 chapters 数组，实际返回键: {list(result.keys())}")
        # 兼容：如果返回单个章节对象而非数组
        if result.get("summary") and batch_info:
            logger.warning("检测到单章格式返回，尝试兼容解析")
            return {batch_info[0]["chapter"]: result}

    parsed = {}
    for item in chapters_list:
        if isinstance(item, dict) and isinstance(item.get("chapter"), int):
            parsed[item["chapter"]] = item
        else:
            logger.warning(f"跳过无效章节项: {item}")

    if len(parsed) < len(chapters_list):
        logger.warning(f"解析丢失 {len(chapters_list) - len(parsed)} 章")

    return parsed


def validate_chapter_analysis(result: dict, chapter_info: dict) -> list[str]:
    """检查分析结果是否合格，返回问题列表。

    检查项：
    - 摘要长度是否足够（至少 20 字）
    - tension_level 是否在 1-5 范围内
    - 是否识别到出场人物
    """
    errors = []

    summary = result.get("summary", "")
    if len(summary) < 20:
        errors.append(f"章节{chapter_info['chapter']}: 摘要过短({len(summary)}字)")

    tension = result.get("tension_level")
    if tension is not None and not (1 <= tension <= 5):
        errors.append(f"章节{chapter_info['chapter']}: tension_level 不在 1-5 范围")

    if not result.get("characters_appear"):
        errors.append(f"章节{chapter_info['chapter']}: 未识别到出场人物")

    return errors


def _load_existing_chapters(novel_dir: Path) -> dict[int, dict]:
    """加载已分析的章节，用于断点续传。

    优先从 chapters/ 子目录读取（分析过程中的中间文件），
    如果不存在则读取 chapters.yaml（分析完成后的合并文件）。

    返回：
        dict：{章节号: 分析数据}
    """
    chapters_dir = novel_dir / "chapters"
    if chapters_dir.exists():
        result = {}
        for f in chapters_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "chapter" in data:
                result[data["chapter"]] = data
        if result:
            return result

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        return {}
    with open(chapters_file, "r", encoding="utf-8") as f:
        existing = yaml.safe_load(f) or []
    return {ch["chapter"]: ch for ch in existing if isinstance(ch, dict) and "chapter" in ch}


def _append_chapter(novel_dir: Path, chapter_data: dict) -> None:
    """将单章分析结果写入独立文件。

    文件路径：chapters/{章节号}.yaml

    这样做的好处：
    - 每章分析完立即保存，中断也不会丢失
    - 不需要每次重写整个 chapters.yaml（性能更好）
    """
    chapters_dir = novel_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)
    ch_num = chapter_data["chapter"]
    chapter_file = chapters_dir / f"{ch_num:04d}.yaml"
    with open(chapter_file, "w", encoding="utf-8") as f:
        yaml.dump(chapter_data, f, allow_unicode=True, default_flow_style=False)


def _merge_chapters(novel_dir: Path) -> None:
    """合并所有独立章节文件为 chapters.yaml。

    在分析完成后调用，生成一个完整快照供其他脚本使用。
    """
    chapters_dir = novel_dir / "chapters"
    if not chapters_dir.exists():
        return
    all_chapters = []
    for f in sorted(chapters_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            all_chapters.append(data)
    all_chapters.sort(key=lambda x: x.get("chapter", 0))
    chapters_file = novel_dir / "chapters.yaml"
    with open(chapters_file, "w", encoding="utf-8") as f:
        yaml.dump(all_chapters, f, allow_unicode=True, default_flow_style=False)
    logger.info(f"已合并 {len(all_chapters)} 章 → chapters.yaml")


def _get_batch_size(config: dict) -> int:
    """读取批量大小配置，确保返回有效整数。"""
    raw = config["llm"].get("chapter_batch_size", 1)
    try:
        batch_size = int(raw)
    except (TypeError, ValueError):
        batch_size = 1
    return max(1, batch_size)


def chapter_analyze(material_id: str) -> None:
    """对指定小说进行章节分析（支持断点续传）。

    流程：
    1. 加载章节索引和原文
    2. 检查已分析的章节（断点续传）
    3. 批量或逐章分析待处理章节
    4. 合并结果并执行质量检查

    参数：
        material_id：素材 ID（如 nm_novel_20240101_abc1）
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"小说目录不存在: {novel_dir}")
        return

    config = load_config()

    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.split("\n")

    # 加载已分析的章节（断点续传）
    done = _load_existing_chapters(novel_dir)
    if done:
        logger.info(f"断点续传：已完成 {len(done)} 章，从第 {max(done.keys()) + 1} 章继续")

    total = len(chapter_index)
    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    batch_size = _get_batch_size(config)
    completed = 0
    skipped = 0

    # 过滤出待处理章节
    pending = [ch for ch in chapter_index if ch["chapter"] not in done]
    skipped = total - len(pending)

    if not pending:
        logger.info(f"所有 {total} 章已完成，跳过分析")
    else:
        n_batches = (len(pending) + batch_size - 1) // batch_size
        logger.info(f"待分析: {len(pending)} 章，批量大小: {batch_size}，共 {n_batches} 批次")

    for batch_idx, batch_start in enumerate(range(0, len(pending), batch_size)):
        batch = pending[batch_start:batch_start + batch_size]
        first_ch = batch[0]["chapter"]
        last_ch = batch[-1]["chapter"]

        logger.info(f"[批次 {batch_idx + 1}/{n_batches}] 第 {first_ch}-{last_ch} 章（共 {len(batch)} 章）")

        # 批量分析
        batch_results: dict[int, dict] = {}
        use_batch_mode = batch_size > 1 and len(batch) > 1
        if use_batch_mode:
            try:
                batch_results = analyze_chapters_batch(batch, lines, config)
                if len(batch_results) < len(batch):
                    missing = [ch["chapter"] for ch in batch if ch["chapter"] not in batch_results]
                    logger.warning(f"批量返回不完整，缺失 {len(missing)} 章（将单章降级）: {missing}")
            except Exception as e:
                logger.warning(f"批量分析失败: {e}，降级为逐章模式")

        # 处理每章结果
        for ch_info in batch:
            ch_num = ch_info["chapter"]
            result = batch_results.get(ch_num)

            if result is None:
                # 批量失败或缺漏，改用单章分析
                if use_batch_mode:
                    logger.info(f"[单章] 第 {ch_num} 章: {ch_info['title']}")
                chapter_text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])
                try:
                    result = analyze_chapter(chapter_text, ch_info, config)
                except Exception as e:
                    logger.error(f"第 {ch_num} 章分析失败（已重试耗尽）: {e}")
                    continue

            # 检查结果质量
            errors = validate_chapter_analysis(result, ch_info)
            for err in errors:
                logger.warning(err)

            result["chapter"] = ch_num
            result["title"] = ch_info["title"]

            # 立即保存（断点续传关键）
            _append_chapter(novel_dir, result)
            completed += 1

        # 批次间等待（避免触发速率限制）
        if batch_start + batch_size < len(pending):
            time.sleep(rate_limit)

    logger.info(f"章级分析完成: 新分析 {completed} 章，跳过已完成 {skipped} 章，共 {total} 章")

    # 合并所有章节文件
    _merge_chapters(novel_dir)

    # 质量检查
    logger.info("执行章级分析质量校验...")
    if not run_quality_check(material_id):
        update_meta_status(material_id, "failed")
        raise ValueError(f"章级分析质量校验未通过：{material_id}")

    update_meta_status(material_id, "analyzed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python analyze.py <material_id>")
        sys.exit(1)

    chapter_analyze(sys.argv[1])