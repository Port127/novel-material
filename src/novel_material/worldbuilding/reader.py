"""世界观产物的新旧格式统一读取器。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from novel_material.infra.yaml_io import load_yaml, load_yaml_list

from .models import (
    WorldbuildingDimension,
    WorldbuildingEntity,
    WorldbuildingIndex,
    WorldbuildingOverview,
    WorldbuildingRelation,
    WorldbuildingView,
)


def load_worldbuilding_view(novel_dir: Path) -> WorldbuildingView:
    """读取 layered 或 legacy 世界观为统一只读视图。"""
    wb_dir = Path(novel_dir) / "worldbuilding"
    index_data = load_yaml(wb_dir / "_index.yaml")
    layout = "layered" if index_data.get("layout") == "layered" else "legacy"
    if layout == "layered":
        return _load_layered_view(wb_dir, index_data)
    return _load_legacy_view(wb_dir, index_data)


def _load_layered_view(wb_dir: Path, index_data: dict[str, Any]) -> WorldbuildingView:
    index = WorldbuildingIndex(**{"layout": "layered", **index_data})
    overview_data = load_yaml(wb_dir / "overview.yaml")
    overview = WorldbuildingOverview(**overview_data) if overview_data else None
    dimensions_data = load_yaml(wb_dir / "dimensions.yaml")
    dimensions = tuple(
        WorldbuildingDimension(**item)
        for item in dimensions_data.get("dimensions", [])
        if isinstance(item, dict)
    )
    entities = tuple(_load_layered_entities(wb_dir / "entities"))
    relations_data = load_yaml(wb_dir / "relations.yaml")
    relations = tuple(
        WorldbuildingRelation(**item)
        for item in relations_data.get("relations", [])
        if isinstance(item, dict)
    )
    return WorldbuildingView(
        layout="layered",
        index=index,
        overview=overview,
        dimensions=dimensions,
        entities=entities,
        relations=relations,
    )


def _load_layered_entities(entities_dir: Path) -> list[WorldbuildingEntity]:
    entities: list[WorldbuildingEntity] = []
    for path in sorted(entities_dir.glob("*.yaml")):
        data = load_yaml(path)
        if data:
            entities.append(WorldbuildingEntity(**data))
    return entities


def _load_legacy_view(wb_dir: Path, index_data: dict[str, Any]) -> WorldbuildingView:
    entities = [
        *_load_legacy_factions(wb_dir),
        *_load_legacy_regions(wb_dir),
        *_load_legacy_power_systems(wb_dir),
    ]
    index = WorldbuildingIndex(
        layout="legacy",
        entity_count=len(entities),
        llm_success=bool(index_data.get("llm_success")),
        legacy_counts=dict(index_data),
    )
    return WorldbuildingView(
        layout="legacy",
        index=index,
        entities=tuple(entities),
    )


def _load_legacy_factions(wb_dir: Path) -> list[WorldbuildingEntity]:
    return [
        _legacy_entity("factions", item)
        for item in _load_first_list(wb_dir, ("factions.yaml",))
        if isinstance(item, dict)
    ]


def _load_legacy_regions(wb_dir: Path) -> list[WorldbuildingEntity]:
    regions: list[dict[str, Any]] = []
    for filename in ("regions.yaml", "geography.yaml"):
        path = wb_dir / filename
        mapping = load_yaml(path)
        if mapping:
            raw_regions = mapping.get("regions", [])
            if isinstance(raw_regions, list):
                regions = [item for item in raw_regions if isinstance(item, dict)]
                break
        loaded_list = load_yaml_list(path)
        if loaded_list:
            regions = [item for item in loaded_list if isinstance(item, dict)]
            break
    return [_legacy_entity("regions", item) for item in regions]


def _load_legacy_power_systems(wb_dir: Path) -> list[WorldbuildingEntity]:
    entities: list[WorldbuildingEntity] = []
    for filename in ("power_systems.yaml", "power_system.yaml"):
        path = wb_dir / filename
        mapping = load_yaml(path)
        if mapping:
            entities.append(_legacy_power_system_entity(mapping))
            break
        loaded_list = load_yaml_list(path)
        if loaded_list:
            entities.extend(
                _legacy_entity("power_systems", item)
                for item in loaded_list
                if isinstance(item, dict)
            )
            break
    return entities


def _load_first_list(wb_dir: Path, filenames: tuple[str, ...]) -> list[dict[str, Any]]:
    for filename in filenames:
        loaded = load_yaml_list(wb_dir / filename)
        if loaded:
            return [item for item in loaded if isinstance(item, dict)]
    return []


def _legacy_power_system_entity(data: dict[str, Any]) -> WorldbuildingEntity:
    return _legacy_entity(
        "power_systems",
        {
            "name": data.get("name") or "力量体系",
            "description": data.get("description", ""),
            "importance": data.get("importance", "primary"),
            "properties": {
                "levels": data.get("levels", []),
                "rules": data.get("rules", []),
            },
        },
    )


def _legacy_entity(entity_type: str, data: dict[str, Any]) -> WorldbuildingEntity:
    name = str(data.get("name") or "")
    properties = data.get("properties")
    if not isinstance(properties, dict):
        properties = {
            key: value
            for key, value in data.items()
            if key
            not in {
                "name",
                "description",
                "importance",
                "first_appearance",
                "first_appearance_chapter",
            }
        }
    return WorldbuildingEntity(
        id=_legacy_entity_id(entity_type, name),
        type=entity_type,
        name=name,
        description=str(data.get("description") or ""),
        properties=properties,
        importance=_normalize_importance(data.get("importance")),
        first_appearance_chapter=_coerce_chapter(
            data.get("first_appearance_chapter", data.get("first_appearance"))
        ),
        confidence=0.0,
    )


def _legacy_entity_id(entity_type: str, name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    if not slug:
        slug = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{entity_type}_{slug}"


def _normalize_importance(value: object) -> str:
    if value in {"primary", "secondary", "minor"}:
        return str(value)
    return "secondary"


def _coerce_chapter(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


__all__ = ["load_worldbuilding_view"]
