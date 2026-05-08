"""质量校验脚本：结合结构校验与内容质量校验。"""
import sys
import yaml
import re

from novel_material.infra.config import NOVELS_DIR, get_settings
from .schema import validate_material


def _jaccard_similarity(text1: str, text2: str) -> float:
    """计算两个文本的 Jaccard 相似度（基于词汇重叠）。

    参数：
        text1: 第一个文本
        text2: 第二个文本

    返回：
        相似度值 (0.0-1.0)
    """
    # 使用字符集进行相似度计算（适合中文）
    chars1 = set(text1)
    chars2 = set(text2)

    if not chars1 or not chars2:
        return 0.0

    intersection = len(chars1 & chars2)
    union = len(chars1 | chars2)

    return intersection / union if union > 0 else 0.0


def check_summary_similarity(
    material_id: str,
    window_size: int = 10,
    threshold: float = 0.7,
    start_ch: int | None = None,
    end_ch: int | None = None
) -> list[str]:
    """检查摘要相似度，发现模式化输出。

    参数：
        material_id: 素材 ID
        window_size: 采样窗口（最近多少章进行比较）
        threshold: 相似度阈值（超过此值发出警告）
        start_ch: 起始章节号
        end_ch: 结束章节号

    返回：
        警告列表（相似度超标的章节对）
    """
    chapters_file = NOVELS_DIR / material_id / "chapters.yaml"
    if not chapters_file.exists():
        return []

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    warnings: list[str] = []

    # 范围过滤
    filtered_chapters = [
        ch for ch in chapters
        if isinstance(ch, dict)
        and (start_ch is None or ch.get("chapter", 0) >= start_ch)
        and (end_ch is None or ch.get("chapter", 0) <= end_ch)
    ]

    # 按章节号排序
    filtered_chapters.sort(key=lambda x: x.get("chapter", 0))

    # 使用滑动窗口检查相似度
    # 对于每个章节，检查它与窗口内其他章节的相似度
    for i in range(len(filtered_chapters)):
        ch1 = filtered_chapters[i]
        summary1 = ch1.get("summary", "")
        if not summary1:
            continue

        # 检查窗口内的其他章节（向前 window_size 章）
        window_start = max(0, i - window_size)
        for j in range(window_start, i):
            ch2 = filtered_chapters[j]
            summary2 = ch2.get("summary", "")
            if not summary2:
                continue

            sim = _jaccard_similarity(summary1, summary2)
            if sim > threshold:
                ch_num1 = ch1.get("chapter", "?")
                ch_num2 = ch2.get("chapter", "?")
                warnings.append(
                    f"第{ch_num1}章与第{ch_num2}章摘要相似度高({sim:.2f})，"
                    f"可能存在模式化输出"
                )

    # 限制警告数量，避免过多
    unique_warnings = []
    seen = set()
    for w in warnings:
        # 提取章节号作为唯一标识
        match = re.search(r"第(\d+)章与第(\d+)章", w)
        if match:
            key = (int(match.group(1)), int(match.group(2)))
            if key not in seen:
                seen.add(key)
                unique_warnings.append(w)

    return unique_warnings[:20]  # 最多返回 20 条警告


def check_summary_quality(material_id: str, start_ch: int | None = None, end_ch: int | None = None) -> tuple[list[str], list[str]]:
    """检查摘要质量，返回 (errors, warnings)。

    参数：
        material_id：素材 ID
        start_ch：起始章节号（可选，用于部分分析）
        end_ch：结束章节号（可选，用于部分分析）
    """
    chapters_file = NOVELS_DIR / material_id / "chapters.yaml"
    if not chapters_file.exists():
        return [], []

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    errors: list[str] = []
    warnings: list[str] = []

    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        ch_num = ch.get("chapter", "?")

        # 范围过滤
        if start_ch is not None and isinstance(ch_num, int) and ch_num < start_ch:
            continue
        if end_ch is not None and isinstance(ch_num, int) and ch_num > end_ch:
            continue

        summary = ch.get("summary", "")
        if len(summary) < 50:
            errors.append(f"第{ch_num}章: 摘要过短（{len(summary)}字，要求 ≥50）")
        if len(summary) > 200:
            warnings.append(f"第{ch_num}章: 摘要过长（{len(summary)}字，建议 ≤200）")
        funcs = ch.get("chapter_functions", ch.get("chapter_function", []))
        if not funcs:
            warnings.append(f"第{ch_num}章: 未标注章节功能（chapter_functions 为空）")

    return errors, warnings


def check_coverage(material_id: str, start_ch: int | None = None, end_ch: int | None = None) -> list[str]:
    """检查分析覆盖率。

    参数：
        material_id：素材 ID
        start_ch：起始章节号（可选，用于部分分析）
        end_ch：结束章节号（可选，用于部分分析）
    """
    novel_dir = NOVELS_DIR / material_id
    index_file = novel_dir / "chapter_index.yaml"
    chapters_file = novel_dir / "chapters.yaml"

    if not index_file.exists() or not chapters_file.exists():
        return []

    with open(index_file, "r", encoding="utf-8") as f:
        index = yaml.safe_load(f) or []
    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    # 计算范围内的章节总数
    chapters_in_range = [
        ch for ch in index
        if (start_ch is None or ch.get("chapter") >= start_ch)
        and (end_ch is None or ch.get("chapter") <= end_ch)
    ]
    total = len(chapters_in_range)

    # 计算范围内已分析的章节
    analyzed_ch_nums = {c.get("chapter") for c in chapters if isinstance(c, dict) and "chapter" in c}
    analyzed_in_range = [
        ch for ch in chapters_in_range
        if ch.get("chapter") in analyzed_ch_nums
    ]
    analyzed = len(analyzed_in_range)
    missing = total - analyzed

    if missing > 0:
        range_desc = ""
        if start_ch is not None or end_ch is not None:
            range_start = start_ch or 1
            range_end = end_ch or len(index)
            range_desc = f"（第 {range_start}-{range_end} 章）"
        return [f"覆盖率不足{range_desc}：范围内 {total} 章，已分析 {analyzed}，缺少 {missing} 章"]
    return []


def run_quality_check(material_id: str, start_ch: int | None = None, end_ch: int | None = None) -> bool:
    """运行完整质量校验，返回 True 表示通过。

    参数：
        material_id：素材 ID
        start_ch：起始章节号（可选，用于部分分析）
        end_ch：结束章节号（可选，用于部分分析）
    """
    range_desc = ""
    if start_ch is not None or end_ch is not None:
        novel_dir = NOVELS_DIR / material_id
        index_file = novel_dir / "chapter_index.yaml"
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                index = yaml.safe_load(f) or []
            range_start = start_ch or 1
            range_end = end_ch or len(index)
            range_desc = f"（第 {range_start}-{range_end} 章）"

    print(f"\n{'='*50}")
    print(f"质量校验：{material_id}{range_desc}")
    print(f"{'='*50}")

    # Schema 结构校验
    print("\n[Schema 结构校验]")
    schema_ok = validate_material(material_id, verbose=True)

    # 内容质量校验
    print("\n[内容质量校验]")
    content_errors, content_warnings = check_summary_quality(material_id, start_ch=start_ch, end_ch=end_ch)
    coverage_errors = check_coverage(material_id, start_ch=start_ch, end_ch=end_ch)

    all_content_errors = content_errors + coverage_errors
    for err in all_content_errors:
        print(f"  ✗ {err}")
    for warn in content_warnings:
        print(f"  ⚠ {warn}")
    if not all_content_errors and not content_warnings:
        print("  ✓ 内容质量校验通过")
    elif not all_content_errors:
        print(f"  ✓ 通过（{len(content_warnings)} 个警告）")

    # 相似度检测（发现模式化输出）
    print("\n[相似度检测]")
    try:
        s = get_settings()
        similarity_window = int(s.get("LLM_SIMILARITY_WINDOW", 10))
        similarity_threshold = float(s.get("LLM_SIMILARITY_WARNING_THRESHOLD", 0.7))
    except (TypeError, ValueError):
        similarity_window = 10
        similarity_threshold = 0.7

    similarity_warnings = check_summary_similarity(
        material_id,
        window_size=similarity_window,
        threshold=similarity_threshold,
        start_ch=start_ch,
        end_ch=end_ch
    )

    for warn in similarity_warnings:
        print(f"  ⚠ {warn}")
    if not similarity_warnings:
        print("  ✓ 相似度检测通过（未发现模式化输出）")
    else:
        print(f"  ⚠ 发现 {len(similarity_warnings)} 个高相似度章节对")

    # 汇总（相似度警告不计入失败条件，仅作为提示）
    passed = schema_ok and len(all_content_errors) == 0
    print(f"\n{'─'*50}")
    if passed:
        print(f"✅ 全部通过：{material_id}")
    else:
        print(f"❌ 校验失败：{material_id}（需修复后重新运行）")

    return passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python quality.py <material_id>")
        sys.exit(1)

    material_id = sys.argv[1]
    ok = run_quality_check(material_id)
    sys.exit(0 if ok else 1)