import re

import pytest

from novel_material.worldbuilding.normalizer import (
    normalize_layered_worldbuilding_response,
    slugify_entity_id,
)


def test_normalizer_builds_stable_entity_ids_and_relation_links() -> None:
    result = normalize_layered_worldbuilding_response(
        {
            "overview": {
                "world_summary": "商业竞争推动剧情",
                "driving_mechanisms": [],
                "confidence": 0.8,
                "limitations": [],
            },
            "dimensions": [
                {
                    "id": "business_rules",
                    "name": "商业规则",
                    "category": "social",
                    "applicability": "applicable",
                    "reason": "主线围绕创业",
                    "confidence": 0.8,
                }
            ],
            "entities": [
                {
                    "type": "organization",
                    "name": "Jiangling University",
                    "description": "主角初始环境",
                    "importance": "primary",
                    "evidence": [{"chapter": 1, "basis": "fact", "summary": "开篇"}],
                    "confidence": 0.9,
                }
            ],
            "relations": [
                {
                    "source": "Jiangling University",
                    "target": "Jiangling University",
                    "relation_type": "interacts_with",
                    "description": "自引用测试",
                    "evidence": [{"chapter": 1, "basis": "fact", "summary": "证据"}],
                    "confidence": 0.5,
                }
            ],
        }
    )

    assert result.entities[0].id == "organization_jiangling_university"
    assert result.relations[0].source_id == "organization_jiangling_university"
    assert result.index.entity_count == 1
    assert result.index.relation_count == 1
    assert result.index.evidence_count == 2


def test_slugify_entity_id_uses_hash_suffix_for_chinese_names() -> None:
    entity_id = slugify_entity_id("organization", "江陵大学")

    assert re.fullmatch(r"organization_[0-9a-f]{8}", entity_id)
    assert entity_id == slugify_entity_id("organization", "江陵大学")


def test_normalizer_rejects_relation_to_unknown_entity() -> None:
    with pytest.raises(ValueError, match="unknown entity"):
        normalize_layered_worldbuilding_response(
            {
                "overview": {"world_summary": "", "driving_mechanisms": []},
                "dimensions": [],
                "entities": [{"type": "organization", "name": "甲"}],
                "relations": [
                    {
                        "source": "甲",
                        "target": "乙",
                        "relation_type": "conflicts_with",
                    }
                ],
            }
        )


def test_normalizer_rejects_relation_with_unknown_entity_id() -> None:
    with pytest.raises(ValueError, match="unknown entity"):
        normalize_layered_worldbuilding_response(
            {
                "overview": {"world_summary": "", "driving_mechanisms": []},
                "dimensions": [],
                "entities": [
                    {"id": "organization_a", "type": "organization", "name": "甲"}
                ],
                "relations": [
                    {
                        "source_id": "organization_a",
                        "target_id": "organization_missing",
                        "relation_type": "conflicts_with",
                    }
                ],
            }
        )
