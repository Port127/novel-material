from pathlib import Path

from novel_material.infra.yaml_io import save_yaml
from novel_material.worldbuilding.reader import load_worldbuilding_view


def test_layered_worldbuilding_view_loads_entities_and_relations(
    tmp_path: Path,
) -> None:
    wb = tmp_path / "worldbuilding"
    (wb / "entities").mkdir(parents=True)
    save_yaml(
        wb / "_index.yaml",
        {
            "schema_version": "2.0.0",
            "layout": "layered",
            "dimension_count": 1,
            "entity_count": 1,
            "relation_count": 1,
            "evidence_count": 1,
            "legacy_compatible": True,
            "llm_success": True,
        },
    )
    save_yaml(
        wb / "dimensions.yaml",
        {
            "schema_version": "1.0.0",
            "dimensions": [
                {
                    "id": "business_rules",
                    "name": "商业规则",
                    "category": "social",
                    "applicability": "applicable",
                    "reason": "主线围绕创业展开",
                    "confidence": 0.8,
                }
            ],
        },
    )
    save_yaml(
        wb / "overview.yaml",
        {
            "schema_version": "1.0.0",
            "world_summary": "商业竞争推动剧情",
            "driving_mechanisms": [],
            "confidence": 0.7,
            "limitations": [],
        },
    )
    save_yaml(
        wb / "entities" / "organization_jiangling_university.yaml",
        {
            "schema_version": "1.0.0",
            "id": "organization_jiangling_university",
            "type": "organization",
            "name": "江陵大学",
            "description": "主角初始活动环境",
            "importance": "primary",
            "first_appearance_chapter": 1,
            "evidence": [{"chapter": 1, "basis": "fact", "summary": "开篇出现"}],
            "confidence": 0.9,
        },
    )
    save_yaml(
        wb / "relations.yaml",
        {
            "schema_version": "1.0.0",
            "relations": [
                {
                    "id": "rel_0001",
                    "source_id": "organization_jiangling_university",
                    "target_id": "organization_jiangling_university",
                    "relation_type": "interacts_with",
                    "description": "自引用测试关系",
                    "evidence": [{"chapter": 1, "basis": "fact", "summary": "证据"}],
                    "confidence": 0.5,
                }
            ],
        },
    )

    view = load_worldbuilding_view(tmp_path)

    assert view.layout == "layered"
    assert [entity.name for entity in view.entities] == ["江陵大学"]
    assert view.relations[0].source_id == "organization_jiangling_university"
    assert view.dimensions[0].applicability == "applicable"


def test_legacy_worldbuilding_view_is_read_without_rewriting(
    tmp_path: Path,
) -> None:
    wb = tmp_path / "worldbuilding"
    wb.mkdir()
    save_yaml(
        wb / "_index.yaml",
        {
            "power_system_levels": 2,
            "region_count": 1,
            "faction_count": 1,
            "lore_items": 1,
            "llm_success": True,
        },
    )
    save_yaml(
        wb / "factions.yaml",
        [
            {
                "name": "学生会",
                "type": "组织",
                "description": "校园组织",
                "importance": "secondary",
            }
        ],
    )

    before = (wb / "_index.yaml").read_text(encoding="utf-8")
    view = load_worldbuilding_view(tmp_path)
    after = (wb / "_index.yaml").read_text(encoding="utf-8")

    assert view.layout == "legacy"
    assert view.entities[0].name == "学生会"
    assert view.entities[0].type == "factions"
    assert before == after


def test_legacy_geography_and_power_system_are_adapted_to_entities(
    tmp_path: Path,
) -> None:
    wb = tmp_path / "worldbuilding"
    wb.mkdir()
    save_yaml(wb / "_index.yaml", {"llm_success": True})
    save_yaml(
        wb / "geography.yaml",
        {
            "world_name": "江陵",
            "regions": [
                {
                    "name": "江陵大学",
                    "description": "校园主要场景",
                    "importance": "primary",
                }
            ],
        },
    )
    save_yaml(
        wb / "power_system.yaml",
        {
            "name": "商业竞争",
            "description": "现实规则下的资源竞争",
            "levels": [{"name": "创业初期"}],
            "rules": ["现金流约束"],
        },
    )

    view = load_worldbuilding_view(tmp_path)

    by_type = {entity.type: entity for entity in view.entities}
    assert by_type["regions"].name == "江陵大学"
    assert by_type["power_systems"].name == "商业竞争"
    assert by_type["power_systems"].properties["rules"] == ["现金流约束"]
