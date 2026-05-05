#!/usr/bin/env python
"""章级分析：LLM 为每章生成摘要、出场人物、功能标签等。

特性：
- 断点续传：每章分析完立即写入 chapters/{n:04d}.yaml 独立文件（O(1)），全部完成后合并为 chapters.yaml
- tiktoken 动态截断：按 Token 数限制章节输入，不再硬截字符
- 重试由 llm_client.call_llm 统一处理（tenacity 指数退避）
"""
import sys
import yaml
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from scripts.core.paths import NOVELS_DIR, TAGS_FILE
from scripts.core.llm_client import load_config, call_llm, truncate_to_tokens
from scripts.utils.quality_check import run_quality_check
from scripts.utils.tag_validator import flatten_tags

# 每章送给 LLM 的最大 Token 数（章末钩子/转折通常在后半段，保留完整内容）
_MAX_CHAPTER_TOKENS = 1800

_SYSTEM_PROMPT = """你是专业的小说分析助手，负责对每章内容生成摘要和分析。
要求：
1. 摘要 50-100 字，包含关键事件、情感基调、人物互动
2. chapter_function 从标签字典的章节功能标签中选取
3. 准确识别出场人物（仅写名字，不写描述）
4. tension_level 1-5，根据紧张程度评估"""


_CHAPTER_JSON_SCHEMA = """{
  "chapter": 章节号（与输入一致）,
  "summary": "50-100字的章节摘要，包含关键事件、情感基调、人物互动",
  "word_count": 字数,
  "characters_appear": ["出场人物名字列表"],
  "chapter_function": ["章节功能标签，从标准标签中选取"],
  "tension_level": 1-5的整数,
  "pacing": "快/慢/喘息/加速",
  "setting": ["场景类型"],
  "key_plot_point": "如果是关键节点则填写(inciting_incident/midpoint/climax/...，否则留空)"
}"""


def analyze_chapter(content: str, chapter_info: dict, config: dict) -> dict:
    """分析单章内容，返回结构化数据（单章兜底模式）。"""
    model = config["llm"]["model"]
    truncated = truncate_to_tokens(content, _MAX_CHAPTER_TOKENS, model=model)

    user_prompt = f"""请分析以下章节：

章节号：{chapter_info.get('chapter', 'N/A')}
标题：{chapter_info.get('title', 'N/A')}

内容：
{truncated}

请返回 JSON 格式：
{_CHAPTER_JSON_SCHEMA}"""

    return call_llm(_SYSTEM_PROMPT, user_prompt, config)


def analyze_chapters_batch(
    batch_info: list[dict],
    lines: list[str],
    config: dict,
) -> dict[int, dict]:
    """批量分析多章，一次 API 调用返回所有结果。

    相比逐章模式，批量模式将 API 调用次数减少到 1/batch_size，
    在 rate_limit_seconds 较大时（如 10s）可显著缩短总处理时间。

    Returns:
        {chapter_num: result_dict}，仅包含 LLM 成功返回的章节。
        缺失的章节由调用方降级到单章模式处理。
    """
    model = config["llm"]["model"]
    n = len(batch_info)

    # 构建每章内容块
    blocks = []
    for ch_info in batch_info:
        text = "\n".join(lines[ch_info["start_line"]:ch_info["end_line"] + 1])
        truncated = truncate_to_tokens(text, _MAX_CHAPTER_TOKENS, model=model)
        blocks.append(
            f"【第{ch_info['chapter']}章《{ch_info['title']}》】\n{truncated}"
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
{{
  "chapters": [
    {_CHAPTER_JSON_SCHEMA}
  ]
}}"""

    # 输出 token 预算：每章约 400 tokens
    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=n * 450)

    chapters_list = result.get("chapters", [])
    return {
        item["chapter"]: item
        for item in chapters_list
        if isinstance(item, dict) and isinstance(item.get("chapter"), int)
    }


def validate_chapter_analysis(result: dict, chapter_info: dict, valid_funcs: set | None = None) -> list[str]:
    """校验章级分析结果，返回错误列表。"""
    errors = []

    summary = result.get("summary", "")
    if len(summary) < 20:
        errors.append(f"章节{chapter_info['chapter']}: 摘要过短({len(summary)}字)")

    tension = result.get("tension_level")
    if tension is not None and not (1 <= tension <= 5):
        errors.append(f"章节{chapter_info['chapter']}: tension_level 不在 1-5 范围")

    if not result.get("characters_appear"):
        errors.append(f"章节{chapter_info['chapter']}: 未识别到出场人物")

    # 实时校验 chapter_function 标签合法性
    if valid_funcs is not None:
        for func in (result.get("chapter_function") or []):
            if func not in valid_funcs:
                errors.append(
                    f"章节{chapter_info['chapter']}: chapter_function '{func}' 不在标签字典中"
                )

    return errors


def _load_existing_chapters(novel_dir: Path) -> dict[int, dict]:
    """加载已存在的章节分析结果，返回 {chapter_num: data} 映射。

    优先从 chapters/ 子目录读取独立文件（O(1) 断点续传），
    若子目录不存在则兜底读 chapters.yaml（旧格式向后兼容）。
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
    """将单章数据写入独立文件 chapters/{n:04d}.yaml（O(1)，断点续传的核心）。

    每章独立存储，彻底消除"每章重写整个 chapters.yaml"的 O(n²) I/O 瓶颈：
    对 1600 章小说，累计 I/O 从 ~1 GB 降至 ~1.6 MB。
    """
    chapters_dir = novel_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)
    ch_num = chapter_data["chapter"]
    chapter_file = chapters_dir / f"{ch_num:04d}.yaml"
    with open(chapter_file, "w", encoding="utf-8") as f:
        yaml.dump(chapter_data, f, allow_unicode=True, default_flow_style=False)


def _merge_chapters(novel_dir: Path) -> None:
    """合并 chapters/ 子目录中的所有独立文件 → chapters.yaml。

    在 chapter_analyze 完成时调用，产生供下游脚本直接使用的完整快照。
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
    print(f"已合并 {len(all_chapters)} 章 → chapters.yaml")


def chapter_analyze(material_id: str) -> None:
    """对指定小说进行章级分析（支持断点续传）。"""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    config = load_config()

    # 加载章节功能标签合法集（一次性加载，供每章实时校验）
    valid_funcs: set | None = None
    if TAGS_FILE.exists():
        import yaml as _yaml
        tags_dict = _yaml.safe_load(TAGS_FILE.read_text(encoding="utf-8")) or {}
        valid_funcs = flatten_tags(tags_dict.get("chapter_function", {}))
        print(f"已加载章节功能标签字典：{len(valid_funcs)} 个")

    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.split("\n")
    # 加载已完成的章节（断点续传：优先从 chapters/ 独立文件读取）
    done = _load_existing_chapters(novel_dir)
    if done:
        print(f"断点续传：已完成 {len(done)} 章，从第 {max(done.keys()) + 1} 章继续")

    total = len(chapter_index)
    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    batch_size = config["llm"].get("chapter_batch_size", 5)
    completed = 0
    skipped = 0

    # 过滤出待处理章节
    pending = [ch for ch in chapter_index if ch["chapter"] not in done]
    skipped = total - len(pending)

    if not pending:
        print(f"所有 {total} 章已完成，跳过分析")
    else:
        n_batches = (len(pending) + batch_size - 1) // batch_size
        print(f"待分析: {len(pending)} 章，批量大小: {batch_size}，共 {n_batches} 批次")

    for batch_idx, batch_start in enumerate(range(0, len(pending), batch_size)):
        batch = pending[batch_start:batch_start + batch_size]
        first_ch = batch[0]["chapter"]
        last_ch = batch[-1]["chapter"]

        print(f"[批次 {batch_idx + 1}/{n_batches}] 第 {first_ch}-{last_ch} 章（共 {len(batch)} 章）")

        # ── 批量分析 ──
        batch_results: dict[int, dict] = {}
        if len(batch) > 1:
            try:
                batch_results = analyze_chapters_batch(batch, lines, config)
                if len(batch_results) < len(batch):
                    missing = [ch["chapter"] for ch in batch if ch["chapter"] not in batch_results]
                    print(f"  批量返回不完整，缺失 {len(missing)} 章（将单章降级）: {missing}")
            except Exception as e:
                print(f"  批量分析失败: {e}，降级为逐章模式")

        # ── 对每章写结果（批量缺失的降级为单章）──
        for ch_info in batch:
            ch_num = ch_info["chapter"]
            result = batch_results.get(ch_num)

            if result is None:
                # 单章降级分析
                if len(batch) > 1:
                    print(f"  [单章] 第 {ch_num} 章: {ch_info['title']}")
                chapter_text = "\n".join(lines[ch_info["start_line"]:ch_info["end_line"] + 1])
                try:
                    result = analyze_chapter(chapter_text, ch_info, config)
                except Exception as e:
                    print(f"  错误（已重试耗尽）: {e}")
                    print(f"  跳过第 {ch_num} 章，继续处理后续章节")
                    continue

            errors = validate_chapter_analysis(result, ch_info, valid_funcs)
            for err in errors:
                print(f"  警告: {err}")

            result["chapter"] = ch_num
            result["title"] = ch_info["title"]

            # 每章立即写入独立文件（O(1)，断点续传关键）
            _append_chapter(novel_dir, result)
            completed += 1

        if batch_start + batch_size < len(pending):
            time.sleep(rate_limit)

    print(f"\n章级分析完成: 新分析 {completed} 章，跳过已完成 {skipped} 章，共 {total} 章")

    # 合并独立章节文件 → chapters.yaml（供下游脚本使用）
    _merge_chapters(novel_dir)

    # 质量门控：分析完成后自动校验（失败只警告，不阻断写入）
    print("\n执行章级分析质量校验...")
    run_quality_check(material_id)

    # 更新 meta 状态
    meta_file = novel_dir / "meta.yaml"
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)
    meta["status"] = "analyzed"
    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python chapter_analyze.py <material_id>")
        sys.exit(1)

    chapter_analyze(sys.argv[1])
