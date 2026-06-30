"""分层世界观 LLM 响应归一化。"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from novel_material.infra.llm_contracts import require_mapping, require_mapping_list

from .models import (
    LayeredWorldbuilding,
    WorldbuildingDimension,
    WorldbuildingEntity,
    WorldbuildingIndex,
    WorldbuildingOverview,
    WorldbuildingRelation,
)


def slugify_entity_id(entity_type: str, name: str) -> str:
    """生成稳定实体 ID；中文名不依赖拼音，使用 SHA-1 短 hash。"""
    normalized_type = _slug_ascii(entity_type) or "entity"
    normalized_name = _slug_ascii(name)
    if not normalized_name:
        normalized_name = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{normalized_type}_{normalized_name}"


def normalize_layered_worldbuilding_response(payload: object) -> LayeredWorldbuilding:
    """校验 layered 世界观响应并返回内存契约对象。"""
    result = require_mapping(payload, "worldbuilding")
    overview = WorldbuildingOverview(
        **require_mapping(result.get("overview", {}), "worldbuilding.overview")
    )
    dimensions = tuple(
        WorldbuildingDimension(**item)
        for item in require_mapping_list(
            result.get("dimensions", []), "worldbuilding.dimensions"
        )
    )
    entities = _normalize_entities(result.get("entities", []))
    entity_ids_by_name = {entity.name: entity.id for entity in entities}
    entity_ids = {entity.id for entity in entities}
    relations = _normalize_relations(
        result.get("relations", []), entity_ids_by_name, entity_ids
    )
    evidence_count = sum(len(entity.evidence) for entity in entities) + sum(
        len(relation.evidence) for relation in relations
    )
    index = WorldbuildingIndex(
        layout="layered",
        dimension_count=len(dimensions),
        entity_count=len(entities),
        relation_count=len(relations),
        evidence_count=evidence_count,
        legacy_compatible=True,
        llm_success=bool(overview.world_summary or entities),
    )
    return LayeredWorldbuilding(
        index=index,
        overview=overview,
        dimensions=dimensions,
        entities=entities,
        relations=relations,
        dimension_source={},
    )


def _normalize_entities(payload: object) -> tuple[WorldbuildingEntity, ...]:
    entities = []
    for item in require_mapping_list(payload, "worldbuilding.entities"):
        entity_type = str(item.get("type") or "concept")
        name = str(item.get("name") or "")
        if not name:
            raise ValueError("worldbuilding entity name is required")
        data = dict(item)
        data.setdefault("id", slugify_entity_id(entity_type, name))
        data.setdefault("type", entity_type)
        data.setdefault("name", name)
        entities.append(WorldbuildingEntity(**data))
    return tuple(entities)


def _normalize_relations(
    payload: object,
    entity_ids_by_name: dict[str, str],
    entity_ids: set[str],
) -> tuple[WorldbuildingRelation, ...]:
    relations = []
    for index, item in enumerate(
        require_mapping_list(payload, "worldbuilding.relations"), start=1
    ):
        data = dict(item)
        source_id = data.get("source_id") or _resolve_relation_endpoint(
            data.get("source"), entity_ids_by_name
        )
        target_id = data.get("target_id") or _resolve_relation_endpoint(
            data.get("target"), entity_ids_by_name
        )
        _require_known_entity_id(source_id, entity_ids)
        _require_known_entity_id(target_id, entity_ids)
        data["source_id"] = source_id
        data["target_id"] = target_id
        data.setdefault("id", f"rel_{index:04d}")
        relations.append(WorldbuildingRelation(**data))
    return tuple(relations)


def _require_known_entity_id(value: object, entity_ids: set[str]) -> None:
    entity_id = str(value or "")
    if entity_id not in entity_ids:
        raise ValueError(f"unknown entity in relation: {entity_id}")


def _resolve_relation_endpoint(
    value: object,
    entity_ids_by_name: dict[str, str],
) -> str:
    name = str(value or "")
    entity_id = entity_ids_by_name.get(name)
    if not entity_id:
        raise ValueError(f"unknown entity in relation: {name}")
    return entity_id


def _slug_ascii(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return re.sub(r"_+", "_", slug)


__all__ = [
    "normalize_layered_worldbuilding_response",
    "slugify_entity_id",
]
