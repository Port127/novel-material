"""分层世界观的只读契约模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorldbuildingEvidence(BaseModel):
    """世界观实体或关系的章节证据。"""

    model_config = ConfigDict(frozen=True)

    chapter: int | None = None
    basis: Literal["fact", "inference"] = "fact"
    summary: str = ""


class WorldbuildingDimension(BaseModel):
    """本书适用或不适用的世界观维度。"""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str = ""
    category: str = ""
    applicability: Literal["applicable", "not_applicable", "uncertain"]
    reason: str = ""
    confidence: float = 0.0


class WorldbuildingOverview(BaseModel):
    """世界观运行机制概览。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0.0"
    world_summary: str = ""
    driving_mechanisms: tuple[dict[str, Any], ...] = ()
    confidence: float = 0.0
    limitations: tuple[str, ...] = ()


class WorldbuildingEntity(BaseModel):
    """世界观实体卡片。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0.0"
    id: str
    type: str
    name: str
    aliases: tuple[str, ...] = ()
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    importance: Literal["primary", "secondary", "minor"] = "secondary"
    first_appearance_chapter: int | None = None
    key_appearances: tuple[dict[str, Any], ...] = ()
    evidence: tuple[WorldbuildingEvidence, ...] = ()
    confidence: float = 0.0
    source_quality: str = "llm_verified"
    dimension_id: str | None = None


class WorldbuildingRelation(BaseModel):
    """世界观实体之间的关系。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0.0"
    id: str
    source_id: str
    target_id: str
    relation_type: str
    description: str = ""
    evolution: tuple[dict[str, Any], ...] = ()
    evidence: tuple[WorldbuildingEvidence, ...] = ()
    confidence: float = 0.0


class WorldbuildingIndex(BaseModel):
    """世界观目录摘要。"""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "2.0.0"
    layout: Literal["layered", "legacy"] = "legacy"
    dimension_count: int = 0
    entity_count: int = 0
    relation_count: int = 0
    evidence_count: int = 0
    legacy_compatible: bool = True
    llm_success: bool = False
    created_at: str | None = None
    legacy_counts: dict[str, Any] = Field(default_factory=dict)
    dimension_status: dict[str, str] = Field(default_factory=dict)
    source_quality_counts: dict[str, int] = Field(default_factory=dict)


class WorldbuildingView(BaseModel):
    """新旧世界观统一只读视图。"""

    model_config = ConfigDict(frozen=True)

    layout: Literal["layered", "legacy"]
    index: WorldbuildingIndex
    overview: WorldbuildingOverview | None = None
    dimensions: tuple[WorldbuildingDimension, ...] = ()
    entities: tuple[WorldbuildingEntity, ...] = ()
    relations: tuple[WorldbuildingRelation, ...] = ()


class LayeredWorldbuilding(BaseModel):
    """layered 世界观写入前的完整内存对象。"""

    model_config = ConfigDict(frozen=True)

    index: WorldbuildingIndex
    overview: WorldbuildingOverview
    dimensions: tuple[WorldbuildingDimension, ...] = ()
    entities: tuple[WorldbuildingEntity, ...] = ()
    relations: tuple[WorldbuildingRelation, ...] = ()
    dimension_source: dict[str, Any] = Field(default_factory=dict)
