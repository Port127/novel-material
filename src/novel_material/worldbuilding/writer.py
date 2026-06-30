"""分层世界观文件写入器。"""

from __future__ import annotations

from pathlib import Path

from novel_material.infra.yaml_io import save_yaml

from .models import LayeredWorldbuilding


def write_layered_worldbuilding(novel_dir: Path, layered: LayeredWorldbuilding) -> None:
    """写入 layered worldbuilding 目录结构。"""
    wb_dir = Path(novel_dir) / "worldbuilding"
    entities_dir = wb_dir / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    _clear_yaml_files(entities_dir)

    save_yaml(wb_dir / "_index.yaml", layered.index.model_dump(mode="json"))
    save_yaml(wb_dir / "overview.yaml", layered.overview.model_dump(mode="json"))
    save_yaml(
        wb_dir / "dimensions.yaml",
        {
            "schema_version": "1.0.0",
            "source": _json_safe(layered.dimension_source),
            "dimensions": [
                item.model_dump(mode="json") for item in layered.dimensions
            ],
        },
    )
    for entity in layered.entities:
        save_yaml(entities_dir / f"{entity.id}.yaml", entity.model_dump(mode="json"))
    save_yaml(
        wb_dir / "relations.yaml",
        {
            "schema_version": "1.0.0",
            "relations": [
                item.model_dump(mode="json") for item in layered.relations
            ],
        },
    )


def _clear_yaml_files(directory: Path) -> None:
    for path in directory.glob("*.yaml"):
        path.unlink()


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


__all__ = ["write_layered_worldbuilding"]
