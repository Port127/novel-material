"""Schema 结构校验器：基于 pydantic 对核心 YAML 文件做结构验证。

此模块作为统一入口，从 models.py 导入 Pydantic 模型，从 validators.py 导入校验函数。
保持向后兼容，所有导出与原文件一致。
"""
import sys

from novel_material.validation.models import (
    MetaModel,
    ChapterEntryModel,
    EvaluationModel,
    NovelTagsModel,
    _MATERIAL_ID_PATTERN,
    _VALID_STATUSES,
    _VALID_PACING,
)
from novel_material.validation.validators import (
    validate_meta,
    validate_chapters,
    get_schema_error_chapters,
    validate_novel_tags,
    validate_chapter_tags_fields,
    validate_chapter_tags,
    validate_evaluation,
    validate_material,
)

__all__ = [
    # 模型
    "MetaModel",
    "ChapterEntryModel",
    "EvaluationModel",
    "NovelTagsModel",
    # 常量
    "_MATERIAL_ID_PATTERN",
    "_VALID_STATUSES",
    "_VALID_PACING",
    # 校验函数
    "validate_meta",
    "validate_chapters",
    "get_schema_error_chapters",
    "validate_novel_tags",
    "validate_chapter_tags_fields",
    "validate_chapter_tags",
    "validate_evaluation",
    "validate_material",
]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python schema.py <material_id>")
        sys.exit(1)

    ok = validate_material(sys.argv[1])
    sys.exit(0 if ok else 1)