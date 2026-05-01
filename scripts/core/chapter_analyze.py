#!/usr/bin/env python
"""章级分析：LLM 为每章生成摘要、出场人物、功能标签等。

特性：
- 断点续传：每章分析完立即追加写入 chapters.yaml，中断后重启自动跳过已完成章节
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

# 每章送给 LLM 的最大 Token 数（章末钩子/转折通常在后半段，保留完整内容）
_MAX_CHAPTER_TOKENS = 1800


def analyze_chapter(content: str, chapter_info: dict, config: dict) -> dict:
    """分析单章内容，返回结构化数据。"""
    llm_config = config.get("chapter_analyze", {})
    system_prompt = llm_config.get("system_prompt", "")
    model = config["llm"]["model"]

    # 动态截断：按 Token 数而非字符数
    truncated = truncate_to_tokens(content, _MAX_CHAPTER_TOKENS, model=model)

    user_prompt = f"""请分析以下章节：

章节号：{chapter_info.get('chapter', 'N/A')}
标题：{chapter_info.get('title', 'N/A')}

内容：
{truncated}

请返回 JSON 格式：
{{
  "summary": "50-100字的章节摘要，包含关键事件、情感基调、人物互动",
  "word_count": 字数,
  "characters_appear": ["出场人物名字列表"],
  "chapter_function": ["章节功能标签，从标准标签中选取"],
  "tension_level": 1-5的整数,
  "pacing": "快/慢/喘息/加速",
  "setting": ["场景类型"],
  "key_plot_point": "如果是关键节点则填写(inciting_incident/midpoint/climax/...，否则留空)"
}}"""

    return call_llm(system_prompt, user_prompt, config)


def validate_chapter_analysis(result: dict, chapter_info: dict) -> list[str]:
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

    return errors


def _load_existing_chapters(chapters_file: Path) -> dict[int, dict]:
    """加载已存在的章节分析结果，返回 {chapter_num: data} 映射。"""
    if not chapters_file.exists():
        return {}
    with open(chapters_file, "r", encoding="utf-8") as f:
        existing = yaml.safe_load(f) or []
    return {ch["chapter"]: ch for ch in existing if isinstance(ch, dict) and "chapter" in ch}


def _append_chapter(chapters_file: Path, chapter_data: dict) -> None:
    """将单章数据追加写入 chapters.yaml（断点续传的核心）。"""
    existing = []
    if chapters_file.exists():
        with open(chapters_file, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or []

    # 更新或追加
    updated = False
    for i, ch in enumerate(existing):
        if isinstance(ch, dict) and ch.get("chapter") == chapter_data["chapter"]:
            existing[i] = chapter_data
            updated = True
            break
    if not updated:
        existing.append(chapter_data)

    with open(chapters_file, "w", encoding="utf-8") as f:
        yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)


def chapter_analyze(material_id: str) -> None:
    """对指定小说进行章级分析（支持断点续传）。"""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    config = load_config()

    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.split("\n")
    chapters_file = novel_dir / "chapters.yaml"

    # 加载已完成的章节（断点续传）
    done = _load_existing_chapters(chapters_file)
    if done:
        print(f"断点续传：已完成 {len(done)} 章，从第 {max(done.keys()) + 1} 章继续")

    total = len(chapter_index)
    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    completed = 0
    skipped = 0

    for i, ch_info in enumerate(chapter_index):
        ch_num = ch_info["chapter"]

        # 跳过已完成章节
        if ch_num in done:
            skipped += 1
            continue

        start_line = ch_info["start_line"]
        end_line = ch_info["end_line"]
        chapter_text = "\n".join(lines[start_line:end_line + 1])

        print(f"[{ch_num}/{total}] 分析: {ch_info['title']}")

        try:
            result = analyze_chapter(chapter_text, ch_info, config)
        except Exception as e:
            print(f"  错误（已重试耗尽）: {e}")
            print(f"  跳过第 {ch_num} 章，继续处理后续章节")
            continue

        errors = validate_chapter_analysis(result, ch_info)
        for err in errors:
            print(f"  警告: {err}")

        result["chapter"] = ch_num
        result["title"] = ch_info["title"]

        # 每章立即写入磁盘（断点续传关键）
        _append_chapter(chapters_file, result)
        completed += 1

        if i < total - 1:
            time.sleep(rate_limit)

    print(f"\n章级分析完成: 新分析 {completed} 章，跳过已完成 {skipped} 章，共 {total} 章")

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
