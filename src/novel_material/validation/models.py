"""Pydantic 模型定义：用于 YAML 文件结构校验的数据模型。

此模块包含所有 Pydantic 模型定义，不涉及 IO 操作。
模型用于验证 meta.yaml、chapters.yaml、evaluation.yaml、tags.yaml 等文件的结构。
"""
import re
from typing import Optional, Any

from pydantic import BaseModel, field_validator, Field

from novel_material.infra.config import VALID_STATUSES
from novel_material.validation.pacing_normalize import PACING_CORE, normalize_pacing
from novel_material.infra.common import KEY_PLOT_POINT_VALUES, TENSION_CHANGE_VALUES, HOOK_TYPE_VALUES
from novel_material.schema import FieldSchema

__all__ = [
    "MetaModel",
    "ChapterEntryModel",
    "EvaluationModel",
    "NovelTagsModel",
    "_MATERIAL_ID_PATTERN",
    "_VALID_STATUSES",
    "_VALID_PACING",
]

# 常量
_MATERIAL_ID_PATTERN = re.compile(r"^nm_[a-z]+_\d{8}_[a-z0-9]{4}$")
_VALID_STATUSES = set(VALID_STATUSES)
_VALID_PACING = PACING_CORE  # 使用核心集合，变体已在前置规范化处理

# 从契约加载字段阈值
_SUMMARY_SCHEMA = FieldSchema.load("summary")
_KEY_EVENT_SCHEMA = FieldSchema.load("key_event")
_EMOTION_TRANSITION_SCHEMA = FieldSchema.load("emotion_transition")
_PLOT_PROGRESS_SCHEMA = FieldSchema.load("plot_progress")
_MAIN_THREAD_SUMMARY_SCHEMA = FieldSchema.load("main_thread_summary")
_CORE_CHARACTERS_HINT_SCHEMA = FieldSchema.load("core_characters_hint")
_NOVEL_TYPE_SCHEMA = FieldSchema.load("novel_type")


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
    summary: str = Field(..., min_length=_SUMMARY_SCHEMA.min_length, max_length=_SUMMARY_SCHEMA.max_length)
    tension_level: int = Field(..., ge=1, le=5)
    characters_appear: list = Field(default_factory=list)
    chapter_functions: Optional[list] = None
    pacing: Optional[str] = None
    key_plot_point: Optional[str] = None  # 结构角色标记（代码推断）
    key_event: Optional[str] = Field(None, max_length=_KEY_EVENT_SCHEMA.max_length)  # 关键事件描述（LLM生成）
    # 滑动窗口新增字段（阶段二）
    tension_change: Optional[str] = None  # 张力变化方向（上升/持平/下降）
    emotion_transition: Optional[str] = Field(None, max_length=_EMOTION_TRANSITION_SCHEMA.max_length)  # 情感过渡描述（10-50字）
    plot_progress: Optional[str] = Field(None, max_length=_PLOT_PROGRESS_SCHEMA.max_length)  # 情节进度描述（20-100字）
    # 章节级标签（阶段四新增）
    emotional_tone: Optional[list[str]] = None  # 情感基调（从标签字典选取）
    scene_type: Optional[list[str]] = None  # 场景类型（从标签字典选取）
    technique: Optional[list[str]] = None  # 叙事技巧（从标签字典选取）
    hook_type: Optional[str] = None  # 章末钩子类型

    @field_validator("title")
    @classmethod
    def check_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title 不能为空")
        return v

    @field_validator("pacing")
    @classmethod
    def check_pacing(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # 先规范化再校验（兼容 LLM 输出变体）
        normalized = normalize_pacing(v)
        if normalized not in _VALID_PACING:
            raise ValueError(
                f"pacing 值 '{v}' 规范化后 '{normalized}' 仍不合法，合法值：{_VALID_PACING}"
            )
        return normalized  # 返回规范化后的值

    @field_validator("key_plot_point")
    @classmethod
    def check_key_plot_point(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in KEY_PLOT_POINT_VALUES:
            raise ValueError(
                f"key_plot_point 值 '{v}' 不合法，合法值：{KEY_PLOT_POINT_VALUES}"
            )
        return v

    @field_validator("tension_change")
    @classmethod
    def check_tension_change(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in TENSION_CHANGE_VALUES:
            raise ValueError(
                f"tension_change 值 '{v}' 不合法，合法值：{TENSION_CHANGE_VALUES}"
            )
        return v

    @field_validator("hook_type")
    @classmethod
    def check_hook_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in HOOK_TYPE_VALUES:
            raise ValueError(
                f"hook_type 值 '{v}' 不合法，合法值：{HOOK_TYPE_VALUES}"
            )
        return v


class EvaluationModel(BaseModel):
    """evaluation.yaml 的字段约束。"""
    schema_version: str = Field(..., pattern=r"^2\.0\.1$")
    novel_type: list[str] = Field(..., min_length=_NOVEL_TYPE_SCHEMA.min_length, max_length=_NOVEL_TYPE_SCHEMA.max_length)
    main_thread_summary: str = Field(..., min_length=_MAIN_THREAD_SUMMARY_SCHEMA.min_length, max_length=_MAIN_THREAD_SUMMARY_SCHEMA.max_length)
    total_chapters: int = Field(..., ge=1)
    core_characters_hint: list[str] = Field(..., min_length=_CORE_CHARACTERS_HINT_SCHEMA.min_length, max_length=_CORE_CHARACTERS_HINT_SCHEMA.max_length)
    stage_summaries: dict[int, str] = Field(...)

    @field_validator("novel_type")
    @classmethod
    def check_novel_type(cls, v: list[str]) -> list[str]:
        # 放宽校验：只检查是否为非空字符串，不强制白名单
        # 原因：LLM 可能返回不在字典中的类型，允许后续人工审核
        for t in v:
            if not t or not t.strip():
                raise ValueError(f"novel_type 包含空值")
        return v

    @field_validator("stage_summaries")
    @classmethod
    def check_stage_summaries(cls, v: dict[int, str]) -> dict[int, str]:
        required_stages = {1, 2, 3, 4, 5}
        if set(v.keys()) != required_stages:
            raise ValueError(f"stage_summaries 必须包含5个阶段（1-5），实际：{sorted(v.keys())}")
        return v


class NovelTagsModel(BaseModel):
    """tags.yaml（小说级标签）的最小字段约束。"""
    material_id: str
    channel: Optional[str] = None
    genre_primary: Optional[list[str]] = None  # 支持多主题材
    genre_secondary: Optional[Any] = None
    elements: Optional[Any] = None
    style: Optional[Any] = None
    structure: Optional[str] = None
    setting: Optional[str] = None
    hooks: Optional[Any] = None
    tropes: Optional[Any] = None
    themes: Optional[Any] = None
    # 兼容旧字段
    genre: Optional[Any] = None
    theme: Optional[Any] = None
    tone: Optional[Any] = None

    @field_validator("material_id")
    @classmethod
    def check_material_id(cls, v: str) -> str:
        if not _MATERIAL_ID_PATTERN.match(v):
            raise ValueError(f"material_id 格式不符，实际：{v}")
        return v