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
- Token 截断：每章内容限制在 LLM_MAX_CHAPTER_TOKENS 内（默认 5000）
"""
import sys
import os
import yaml
import time
from pathlib import Path
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR, update_meta_status
from novel_material.infra.llm import load_config, load_provider_config, call_llm, truncate_to_tokens, get_last_call_finish_reason
from novel_material.validation.quality import run_quality_check
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()


def _get_max_chapter_tokens() -> int:
    """读取单章输入截断上限配置。"""
    try:
        return int(os.getenv("LLM_MAX_CHAPTER_TOKENS", "5000"))
    except (TypeError, ValueError):
        return 5000

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
    {"chapter": 1, "summary": "第一章摘要", "characters_appear": ["人物名"], "chapter_functions": ["标签"], "tension_level": 3, "pacing": "快", "setting": ["场景"], "key_plot_point": ""},
    {"chapter": 2, "summary": "第二章摘要", "characters_appear": ["人物名"], "chapter_functions": ["标签"], "tension_level": 2, "pacing": "慢", "setting": ["场景"], "key_plot_point": ""}
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
    truncated = truncate_to_tokens(content, _get_max_chapter_tokens(), model=model)

    user_prompt = f"""请分析以下章节：

章节号：{chapter_info.get('chapter', 'N/A')}
标题：{chapter_info.get('title', 'N/A')}

内容：
{truncated}

请返回 JSON 格式：
{_CHAPTER_JSON_SCHEMA}"""

    timeout = config["llm"].get("analyze_timeout", 300)
    context = f"单章#{chapter_info.get('chapter', 'N/A')}"
    return call_llm(_SYSTEM_PROMPT, user_prompt, config, timeout_override=timeout, context=context)


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
        truncated = truncate_to_tokens(text, _get_max_chapter_tokens(), model=model)
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

    batch_nums = [ch_info["chapter"] for ch_info in batch_info]
    batch_range = f"{min(batch_nums)}-{max(batch_nums)}"
    result = call_llm(
        system_prompt,
        user_prompt,
        config,
        max_tokens_override=n * 1500,
        timeout_override=config["llm"].get("analyze_timeout"),
        context=f"章节分析#批次[{batch_range}]",
        thinking_budget=4000,
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

    # 批次解析质量统计
    returned_count = len(parsed)
    missing_count = n - returned_count
    if missing_count > 0:
        missing = sorted([ch["chapter"] for ch in batch_info if ch["chapter"] not in parsed])
        logger.warning(
            f"批次[{batch_range}] 返回不完整: 期望 {n} 章，实际 {returned_count} 章，"
            f"缺失 {missing_count} 章 {missing}"
        )

    # 每章输出 tokens 分布（从返回数据估算）
    total_summary_chars = sum(len(ch.get("summary", "")) for ch in parsed.values())
    avg_summary_len = total_summary_chars // max(returned_count, 1)
    char_counts = {}
    tension_values = []
    for ch_num, ch_data in parsed.items():
        summary_len = len(ch_data.get("summary", ""))
        char_count = len(ch_data.get("characters_appear", []))
        tension = ch_data.get("tension_level", 0)
        char_counts[ch_num] = {"summary_len": summary_len, "chars": char_count}
        if tension:
            tension_values.append(tension)

    # 输出批次质量摘要
    logger.info(
        f"批次[{batch_range}] 统计: 返回 {returned_count}/{n} 章 | "
        f"摘要平均 {avg_summary_len} 字 | "
        f"张力范围 {min(tension_values) if tension_values else '?'}-{max(tension_values) if tension_values else '?'} | "
        f"finish={get_last_call_finish_reason()}"
    )

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


def chapter_analyze(
    material_id: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
    start_ch: int | None = None,
    end_ch: int | None = None,
    provider: str | None = None,
) -> bool:
    """对指定小说进行章节分析（支持断点续传和范围指定）。

    流程：
    1. 加载章节索引和原文
    2. 检查已分析的章节（断点续传）
    3. 过滤指定范围内的待处理章节
    4. 批量或逐章分析待处理章节
    5. 合并结果并执行质量检查

    参数：
        material_id：素材 ID（如 nm_novel_20240101_abc1）
        progress_callback：可选进度回调函数 (done: int, total: int, desc: str) -> None
        start_ch：起始章节号（可选，不指定则从第一章开始）
        end_ch：结束章节号（可选，不指定则到最后一章）
        provider：服务商名称（可选，不指定则使用默认配置）

    返回：
        True 表示成功，False 表示失败
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"小说目录不存在: {novel_dir}")
        return False

    config = load_provider_config(provider) if provider else load_config()

    # 加载小说基本信息
    meta_file = novel_dir / "meta.yaml"
    meta = {}
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "?")

    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    chapter_count = len(chapter_index)

    # 输出小说基本信息和范围信息
    range_info = ""
    if start_ch is not None or end_ch is not None:
        range_start = start_ch or 1
        range_end = end_ch or chapter_count
        range_info = f" | 分析范围: 第 {range_start}-{range_end} 章"
    logger.info(f"小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}{range_info}")

    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.split("\n")

    # 计算范围内的章节总数
    chapters_in_range = [
        ch for ch in chapter_index
        if (start_ch is None or ch["chapter"] >= start_ch)
        and (end_ch is None or ch["chapter"] <= end_ch)
    ]
    total = len(chapters_in_range)
    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    batch_size = _get_batch_size(config)
    completed = 0
    skipped = 0
    total_downgrades = 0
    total_batch_errors = 0

    # 加载已分析的章节（断点续传）
    done = _load_existing_chapters(novel_dir)
    done_in_range = {
        ch_num: data for ch_num, data in done.items()
        if (start_ch is None or ch_num >= start_ch)
        and (end_ch is None or ch_num <= end_ch)
    }
    if done_in_range:
        if progress_callback:
            progress_callback(len(done_in_range), total, f"断点续传：已完成 {len(done_in_range)} 章")
        else:
            next_ch = max(done_in_range.keys()) + 1
            if start_ch and next_ch < start_ch:
                next_ch = start_ch
            logger.info(f"断点续传：已完成 {len(done_in_range)} 章，从第 {next_ch} 章继续")

    # 过滤出待处理章节（结合断点续传和范围指定）
    pending = [
        ch for ch in chapter_index
        if ch["chapter"] not in done
        and (start_ch is None or ch["chapter"] >= start_ch)
        and (end_ch is None or ch["chapter"] <= end_ch)
    ]
    skipped = total - len(pending)

    if not pending:
        if progress_callback:
            progress_callback(total, total, "所有章节已完成")
        else:
            logger.info(f"所有 {total} 章已完成，跳过分析")
    else:
        n_batches = (len(pending) + batch_size - 1) // batch_size
        if progress_callback:
            progress_callback(skipped, total, f"待分析 {len(pending)} 章")
        else:
            logger.info(f"待分析: {len(pending)} 章，批量大小: {batch_size}，共 {n_batches} 批次")

    for batch_idx, batch_start in enumerate(range(0, len(pending), batch_size)):
        batch = pending[batch_start:batch_start + batch_size]
        first_ch = batch[0]["chapter"]
        last_ch = batch[-1]["chapter"]

        # 批次开始时的日志（非回调模式）
        if not progress_callback:
            logger.info(f"[批次 {batch_idx + 1}/{n_batches}] 第 {first_ch}-{last_ch} 章（共 {len(batch)} 章）")

        batch_start_time = time.monotonic()
        batch_errors = 0
        batch_downgrades = 0
        batch_api_calls = 0

        # 批量分析
        batch_results: dict[int, dict] = {}
        use_batch_mode = batch_size > 1 and len(batch) > 1
        if use_batch_mode:
            try:
                batch_results = analyze_chapters_batch(batch, lines, config)
                batch_api_calls += 1
                if len(batch_results) < len(batch):
                    missing = [ch["chapter"] for ch in batch if ch["chapter"] not in batch_results]
                    batch_downgrades += len(missing)
            except Exception as e:
                logger.warning(f"批量分析失败: {e}，降级为逐章模式")
                batch_errors += 1
                batch_api_calls += 1

        # 处理每章结果
        for ch_info in batch:
            ch_num = ch_info["chapter"]
            result = batch_results.get(ch_num)

            if result is None:
                # 批量失败或缺漏，改用单章分析
                batch_downgrades += 1
                if not progress_callback and use_batch_mode:
                    logger.info(f"[单章] 第 {ch_num} 章: {ch_info['title']}")
                chapter_text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])
                try:
                    result = analyze_chapter(chapter_text, ch_info, config)
                    batch_api_calls += 1
                except Exception as e:
                    logger.error(f"第 {ch_num} 章分析失败（已重试耗尽）: {e}")
                    batch_errors += 1
                    continue

            # 检查结果质量
            errors = validate_chapter_analysis(result, ch_info)
            for err in errors:
                logger.warning(err)
                batch_errors += 1

            result["chapter"] = ch_num
            result["title"] = ch_info["title"]
            result["word_count"] = ch_info.get("word_count", 0)  # 从索引中获取正确字数，防御性取值

            # 立即保存（断点续传关键）
            _append_chapter(novel_dir, result)
            completed += 1

            # 进度更新：在每章完成后更新
            if progress_callback:
                progress_callback(
                    skipped + completed,
                    total,
                    f"第 {first_ch}-{last_ch} 章 ({batch_idx + 1}/{n_batches})"
                )

        # 批次耗时汇总
        batch_elapsed = time.monotonic() - batch_start_time
        total_downgrades += batch_downgrades
        total_batch_errors += batch_errors
        if not progress_callback:
            finish_reason = get_last_call_finish_reason()
            logger.info(
                f"  批次#{batch_idx + 1} 完成: {batch_elapsed:.1f}s | "
                f"返回 {len(batch_results)}/{len(batch)} 章 | "
                f"降级 {batch_downgrades} 次 | "
                f"错误 {batch_errors} 次 | "
                f"finish={finish_reason}"
            )

        # 批次间等待（避免触发速率限制）
        if batch_start + batch_size < len(pending):
            time.sleep(rate_limit)

    if progress_callback:
        progress_callback(total, total, f"完成: {completed} 章")
    else:
        logger.info(f"章级分析完成: 新分析 {completed} 章，跳过已完成 {skipped} 章，共 {total} 章")
        if total_downgrades > 0:
            total_chapters_attempted = n_batches * batch_size if pending else 1
            downgrade_rate = total_downgrades / total_chapters_attempted * 100
            logger.info(
                f"  降级统计: {total_downgrades} 次降级（占 {downgrade_rate:.1f}%），"
                f"批次错误 {total_batch_errors} 次"
            )

    # 合并所有章节文件
    _merge_chapters(novel_dir)

    # 质量检查
    logger.info("执行章级分析质量校验...")
    if not run_quality_check(material_id, start_ch=start_ch, end_ch=end_ch):
        update_meta_status(material_id, "failed")
        raise ValueError(f"章级分析质量校验未通过：{material_id}")

    update_meta_status(material_id, "analyzed")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python analyze.py <material_id>")
        sys.exit(1)

    chapter_analyze(sys.argv[1])