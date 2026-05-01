#!/usr/bin/env python
"""Schema 结构校验器：基于 pydantic 对核心 YAML 文件做结构验证。

校验范围：
  - meta.yaml          → MetaModel
  - chapters.yaml 条目 → ChapterEntryModel
  - tags.yaml（小说级）→ NovelTagsModel

每个 validate_* 函数返回 list[str]（错误描述列表），空列表表示通过。
"""
import re
import sys
import yaml
from pathlib import Path
from typing import Optional, Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pydantic import BaseModel, field_validator, model_validator, Field
from pydantic import ValidationError as PydanticValidationError

from scripts.core.paths import NOVELS_DIR, TAGS_FILE

# ──────────────────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────────────────

_MATERIAL_ID_PATTERN = re.compile(r"^nm_[a-z]+_\d{8}_[a-z0-9]{4}$")

_VALID_STATUSES = {
    "raw", "clean", "analyzed", "indexed",
    "outlined", "tagged", "complete", "backfill-blocked", "refined",
}

_VALID_PACING = {"快", "慢", "喘息", "加速"}


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic 模型
# ──────────────────────────────────────────────────────────────────────────────

class MetaModel(BaseModel):
    """meta.yaml 的最小必填字段约束。"""

    material_id: str
    name: str
    status: str
    word_count: Optional[int] = None
    chapter_count: Optional[int] = None

    @field_validator("material_id")
    @classmethod
    def check_material_id(cls, v: str) -> str:
        if not _MATERIAL_ID_PATTERN.match(v):
            raise ValueError(
                f"material_id 格式不符（期望 nm_{{type}}_YYYYMMDD_{{4位字母数字}}），实际：{v}"
            )
        return v

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(
                f"status 值 '{v}' 不合法，合法值：{sorted(_VALID_STATUSES)}"
            )
        return v

    @field_validator("word_count", "chapter_count", mode="before")
    @classmethod
    def check_positive_int(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if not isinstance(v, int) or v <= 0:
            raise ValueError(f"必须为正整数，实际：{v!r}")
        return v


class ChapterEntryModel(BaseModel):
    """chapters.yaml 单章条目的字段约束。"""

    chapter: int = Field(..., ge=1)
    title: str
    summary: str = Field(..., min_length=20, max_length=500)
    tension_level: int = Field(..., ge=1, le=5)
    characters_appear: list = Field(..., min_length=1)
    chapter_function: Optional[list] = None
    pacing: Optional[str] = None

    @field_validator("title")
    @classmethod
    def check_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title 不能为空")
        return v

    @field_validator("pacing")
    @classmethod
    def check_pacing(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_PACING:
            raise ValueError(
                f"pacing 值 '{v}' 不合法，合法值：{_VALID_PACING}"
            )
        return v

    @field_validator("characters_appear", mode="before")
    @classmethod
    def check_chars_list(cls, v: Any) -> list:
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("characters_appear 必须是非空列表")
        return v


class NovelTagsModel(BaseModel):
    """tags.yaml（小说级标签）的最小字段约束。"""

    material_id: str
    genre: Optional[Any] = None        # list[str] 或 str
    theme: Optional[Any] = None
    tone: Optional[Any] = None

    @field_validator("material_id")
    @classmethod
    def check_material_id(cls, v: str) -> str:
        if not _MATERIAL_ID_PATTERN.match(v):
            raise ValueError(
                f"material_id 格式不符，实际：{v}"
            )
        return v


# ──────────────────────────────────────────────────────────────────────────────
# 校验函数
# ──────────────────────────────────────────────────────────────────────────────

def validate_meta(material_id: str) -> list[str]:
    """校验 meta.yaml，返回错误描述列表（空列表 = 通过）。"""
    meta_file = NOVELS_DIR / material_id / "meta.yaml"
    if not meta_file.exists():
        return [f"meta.yaml 不存在：{meta_file}"]

    with open(meta_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    errors: list[str] = []
    try:
        MetaModel(**{k: data.get(k) for k in MetaModel.model_fields})
    except PydanticValidationError as exc:
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            errors.append(f"meta.yaml [{field}]: {err['msg']}")

    return errors


def validate_chapters(material_id: str) -> list[str]:
    """校验 chapters.yaml 所有条目，返回错误描述列表。"""
    chapters_file = NOVELS_DIR / material_id / "chapters.yaml"
    if not chapters_file.exists():
        return [f"chapters.yaml 不存在：{chapters_file}"]

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    if not chapters:
        return ["chapters.yaml 为空，无章节数据"]

    errors: list[str] = []
    for entry in chapters:
        if not isinstance(entry, dict):
            errors.append("chapters.yaml 包含非字典条目")
            continue

        ch_num = entry.get("chapter", "?")
        try:
            ChapterEntryModel(
                chapter=entry.get("chapter"),
                title=entry.get("title", ""),
                summary=entry.get("summary", ""),
                tension_level=entry.get("tension_level"),
                characters_appear=entry.get("characters_appear", []),
                chapter_function=entry.get(
                    "chapter_function", entry.get("chapter_functions")
                ),
                pacing=entry.get("pacing"),
            )
        except PydanticValidationError as exc:
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                errors.append(f"第{ch_num}章 [{field}]: {err['msg']}")

    return errors


def validate_novel_tags(material_id: str) -> list[str]:
    """校验 tags.yaml（小说级），返回错误描述列表。"""
    tags_file = NOVELS_DIR / material_id / "tags.yaml"
    if not tags_file.exists():
        return []  # tags.yaml 可能还未生成，不视为错误

    with open(tags_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    errors: list[str] = []
    try:
        NovelTagsModel(
            material_id=data.get("material_id", ""),
            genre=data.get("genre"),
            theme=data.get("theme"),
            tone=data.get("tone"),
        )
    except PydanticValidationError as exc:
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            errors.append(f"tags.yaml [{field}]: {err['msg']}")

    return errors


def validate_chapter_tags(material_id: str) -> list[str]:
    """校验 chapters.yaml 中的 chapter_function 标签是否在字典中。"""
    tags_dict_file = TAGS_FILE
    if not tags_dict_file.exists():
        return []  # 无字典则跳过

    with open(tags_dict_file, "r", encoding="utf-8") as f:
        tags_dict = yaml.safe_load(f) or {}

    valid_funcs = tags_dict.get("chapter_function", [])
    if not isinstance(valid_funcs, list) or not valid_funcs:
        return []

    chapters_file = NOVELS_DIR / material_id / "chapters.yaml"
    if not chapters_file.exists():
        return []

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    errors: list[str] = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        ch_num = ch.get("chapter", "?")
        funcs = ch.get("chapter_function", ch.get("chapter_functions", []))
        for func in (funcs or []):
            if func not in valid_funcs:
                errors.append(
                    f"第{ch_num}章 [chapter_function]: '{func}' 不在标签字典中"
                )

    return errors


# ──────────────────────────────────────────────────────────────────────────────
# 综合入口
# ──────────────────────────────────────────────────────────────────────────────

def validate_material(material_id: str, verbose: bool = True) -> bool:
    """对指定素材运行所有校验，返回 True 表示全部通过。

    Args:
        material_id: 素材ID
        verbose: 是否打印详细结果

    Returns:
        bool: True = 通过，False = 存在错误
    """
    all_errors: list[str] = []

    checks = [
        ("meta.yaml 结构校验",        validate_meta),
        ("chapters.yaml 结构校验",     validate_chapters),
        ("小说级标签校验",              validate_novel_tags),
        ("章节功能标签字典校验",         validate_chapter_tags),
    ]

    for label, fn in checks:
        errs = fn(material_id)
        if verbose:
            if errs:
                print(f"  ✗ {label}：{len(errs)} 个错误")
                for e in errs:
                    print(f"      {e}")
            else:
                print(f"  ✓ {label}")
        all_errors.extend(errs)

    passed = len(all_errors) == 0
    if verbose:
        if passed:
            print(f"\nSchema 校验通过：{material_id}")
        else:
            print(f"\nSchema 校验失败：{len(all_errors)} 个错误 [{material_id}]")

    return passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python schema_validator.py <material_id>")
        sys.exit(1)

    ok = validate_material(sys.argv[1])
    sys.exit(0 if ok else 1)
