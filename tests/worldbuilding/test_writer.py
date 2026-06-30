from pathlib import Path

from novel_material.infra.yaml_io import load_yaml
from novel_material.worldbuilding.normalizer import (
    normalize_layered_worldbuilding_response,
)
from novel_material.worldbuilding.writer import write_layered_worldbuilding


def test_write_layered_worldbuilding_outputs_expected_files(tmp_path: Path) -> None:
    layered = normalize_layered_worldbuilding_response(
        {
            "overview": {
                "world_summary": "校园组织驱动剧情",
                "driving_mechanisms": [],
            },
            "dimensions": [
                {
                    "id": "organization_network",
                    "name": "组织网络",
                    "category": "social",
                    "applicability": "applicable",
                    "reason": "多次出现",
                    "confidence": 0.8,
                }
            ],
            "entities": [
                {
                    "type": "organization",
                    "name": "学生会",
                    "description": "校园组织",
                    "importance": "secondary",
                    "evidence": [{"chapter": 1, "basis": "fact", "summary": "出现"}],
                }
            ],
            "relations": [],
        }
    )

    write_layered_worldbuilding(tmp_path, layered)

    assert load_yaml(tmp_path / "worldbuilding" / "_index.yaml")["layout"] == "layered"
    assert (tmp_path / "worldbuilding" / "overview.yaml").is_file()
    assert (tmp_path / "worldbuilding" / "dimensions.yaml").is_file()
    assert len(list((tmp_path / "worldbuilding" / "entities").glob("*.yaml"))) == 1
    assert (tmp_path / "worldbuilding" / "relations.yaml").is_file()


def test_write_layered_worldbuilding_removes_stale_entity_files(
    tmp_path: Path,
) -> None:
    stale = tmp_path / "worldbuilding" / "entities" / "stale.yaml"
    stale.parent.mkdir(parents=True)
    stale.write_text("id: stale\n", encoding="utf-8")
    layered = normalize_layered_worldbuilding_response(
        {
            "overview": {"world_summary": "新世界观", "driving_mechanisms": []},
            "dimensions": [],
            "entities": [{"type": "concept", "name": "新概念"}],
            "relations": [],
        }
    )

    write_layered_worldbuilding(tmp_path, layered)

    assert not stale.exists()
