"""作品画像 work_profile.yaml 的稳定契约模型。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class StoryStructure(BaseModel):
    """作品层面的结构和节奏模式，不替代章节事实。"""

    model_config = ConfigDict(frozen=True)

    pacing_pattern: str = ""
    turning_point_pattern: tuple[str, ...] = ()


class CharacterDynamics(BaseModel):
    """作品层面的人物动力摘要，不替代人物档案。"""

    model_config = ConfigDict(frozen=True)

    ensemble_summary: str = ""
    key_relationship_patterns: tuple[str, ...] = ()


class WorldbuildingDriver(BaseModel):
    """世界观机制如何推动叙事。"""

    model_config = ConfigDict(frozen=True)

    mechanism: str = ""
    narrative_function: str = ""


class TransferableLesson(BaseModel):
    """可迁移写作启示及其适用边界。"""

    model_config = ConfigDict(frozen=True)

    lesson: str
    applies_when: str = ""
    avoid_when: str = ""


class EvidenceIndex(BaseModel):
    """作品画像引用的下层事实产物索引。"""

    model_config = ConfigDict(frozen=True)

    chapters: tuple[int, ...] = ()
    characters: tuple[str, ...] = ()
    worldbuilding_entities: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_any_evidence(self) -> "EvidenceIndex":
        """至少引用一个章节、人物或世界观实体。"""
        if self.chapters or self.characters or self.worldbuilding_entities:
            return self
        raise ValueError("evidence_index 至少需要引用一个下层事实产物")


class WorkProfile(BaseModel):
    """面向写作 Agent 的作品级入口，不作为事实来源。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0.0"
    material_id: str = Field(min_length=1)
    title: str = ""
    quality_level: str = "full"
    core_hooks: tuple[str, ...] = ()
    reader_expectations: tuple[str, ...] = ()
    story_structure: StoryStructure = Field(default_factory=StoryStructure)
    character_dynamics: CharacterDynamics = Field(
        default_factory=CharacterDynamics
    )
    worldbuilding_drivers: tuple[WorldbuildingDriver, ...] = ()
    motifs_and_techniques: tuple[str, ...] = ()
    transferable_lessons: tuple[TransferableLesson, ...] = ()
    evidence_index: EvidenceIndex
    limitations: tuple[str, ...] = ()
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("quality_level")
    @classmethod
    def validate_quality_level(cls, value: str) -> str:
        if value not in {"full", "limited"}:
            raise ValueError("quality_level 必须是 full 或 limited")
        return value


def normalize_work_profile_response(
    payload: object,
    *,
    material_id: str,
    title: str,
) -> WorkProfile:
    """校验 LLM 作品画像响应，并补入素材身份。"""
    if not isinstance(payload, Mapping):
        raise ValueError("work_profile 响应必须是对象")
    data: dict[str, Any] = dict(payload)
    data["material_id"] = material_id
    data["title"] = title
    try:
        return WorkProfile.model_validate(data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


__all__ = [
    "CharacterDynamics",
    "EvidenceIndex",
    "StoryStructure",
    "TransferableLesson",
    "WorkProfile",
    "WorldbuildingDriver",
    "normalize_work_profile_response",
]
