#!/usr/bin/env python
"""质量校验脚本：结合结构校验（schema）与内容质量校验（摘要长度、标签合法性等）。

用法:
    python scripts/utils/quality_check.py <material_id>

退出码：
    0 = 全部通过
    1 = 存在错误
"""
import sys
import yaml
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.core.paths import NOVELS_DIR, TAGS_FILE
from scripts.utils.schema_validator import validate_material


# ──────────────────────────────────────────────────────────────────────────────
# 内容质量校验（独立于 pydantic 结构校验）
# ──────────────────────────────────────────────────────────────────────────────

def check_summary_quality(material_id: str) -> tuple[list[str], list[str]]:
    """检查摘要质量，返回 (errors, warnings)。"""
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
        summary = ch.get("summary", "")
        if len(summary) < 50:
            errors.append(f"第{ch_num}章: 摘要过短（{len(summary)}字，要求 ≥50）")
        if len(summary) > 200:
            warnings.append(f"第{ch_num}章: 摘要过长（{len(summary)}字，建议 ≤200）")
        funcs = ch.get("chapter_functions", ch.get("chapter_function", []))
        if not funcs:
            warnings.append(f"第{ch_num}章: 未标注章节功能（chapter_functions 为空）")

    return errors, warnings


def check_coverage(material_id: str) -> list[str]:
    """检查分析覆盖率：chapters.yaml 章节数 vs chapter_index.yaml 章节数。"""
    novel_dir = NOVELS_DIR / material_id
    index_file = novel_dir / "chapter_index.yaml"
    chapters_file = novel_dir / "chapters.yaml"

    if not index_file.exists() or not chapters_file.exists():
        return []

    with open(index_file, "r", encoding="utf-8") as f:
        index = yaml.safe_load(f) or []
    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    total = len(index)
    analyzed = len([c for c in chapters if isinstance(c, dict)])
    missing = total - analyzed

    if missing > 0:
        return [f"覆盖率不足：总章数 {total}，已分析 {analyzed}，缺少 {missing} 章"]
    return []


# ──────────────────────────────────────────────────────────────────────────────
# 统一入口
# ──────────────────────────────────────────────────────────────────────────────

def run_quality_check(material_id: str) -> bool:
    """运行完整质量校验，返回 True 表示通过。

    流程：
      1. pydantic schema 结构校验（meta + chapters + tags）
      2. 摘要质量 + 章节功能覆盖
      3. 分析覆盖率
    """
    print(f"\n{'='*50}")
    print(f"质量校验：{material_id}")
    print(f"{'='*50}")

    # ── 1. Schema 结构校验 ──
    print("\n[Schema 结构校验]")
    schema_ok = validate_material(material_id, verbose=True)

    # ── 2. 内容质量校验 ──
    print("\n[内容质量校验]")
    content_errors, content_warnings = check_summary_quality(material_id)
    coverage_errors = check_coverage(material_id)

    all_content_errors = content_errors + coverage_errors
    for err in all_content_errors:
        print(f"  ✗ {err}")
    for warn in content_warnings:
        print(f"  ⚠ {warn}")
    if not all_content_errors and not content_warnings:
        print("  ✓ 内容质量校验通过")
    elif not all_content_errors:
        print(f"  ✓ 通过（{len(content_warnings)} 个警告）")

    # ── 汇总 ──
    passed = schema_ok and len(all_content_errors) == 0
    print(f"\n{'─'*50}")
    if passed:
        print(f"✅ 全部通过：{material_id}")
    else:
        total_errs = (0 if schema_ok else 1) + len(all_content_errors)
        print(f"❌ 校验失败：{material_id}（需修复后重新运行）")

    return passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/utils/quality_check.py <material_id>")
        sys.exit(1)

    material_id = sys.argv[1]
    ok = run_quality_check(material_id)
    sys.exit(0 if ok else 1)
