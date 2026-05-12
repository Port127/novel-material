"""数据校验模块。"""

from .schema import validate_material, validate_meta, validate_chapters, validate_novel_tags
from .quality import (
    run_quality_check,
    check_summary_quality,
    check_coverage,
    get_short_summary_chapters,
    get_missing_chapters,
    ChapterIndexNotFoundError,
)
from .tag_rules import check_dimension, suggest_expand

__all__ = [
    "validate_material",
    "validate_meta",
    "validate_chapters",
    "validate_novel_tags",
    "run_quality_check",
    "check_summary_quality",
    "check_coverage",
    "get_short_summary_chapters",
    "get_missing_chapters",
    "ChapterIndexNotFoundError",
    "check_dimension",
    "suggest_expand",
]