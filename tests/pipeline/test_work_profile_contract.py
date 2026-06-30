import pytest

from novel_material.pipeline.work_profile_models import (
    normalize_work_profile_response,
)
from novel_material.pipeline.work_profile_prompt import build_work_profile_prompt


def test_normalize_work_profile_requires_evidence_index() -> None:
    profile = normalize_work_profile_response(
        {
            "core_hooks": ["重生后的商业逆袭"],
            "reader_expectations": ["爽点兑现"],
            "story_structure": {
                "pacing_pattern": "阶段性升级",
                "turning_point_pattern": [],
            },
            "character_dynamics": {
                "ensemble_summary": "人物围绕主角事业展开",
                "key_relationship_patterns": [],
            },
            "worldbuilding_drivers": [
                {
                    "mechanism": "商业竞争",
                    "narrative_function": "制造选择压力",
                }
            ],
            "motifs_and_techniques": ["用日常细节塑造人物"],
            "transferable_lessons": [
                {
                    "lesson": "先给欲望再给阻力",
                    "applies_when": "都市成长线",
                    "avoid_when": "缺少现实规则",
                }
            ],
            "evidence_index": {
                "chapters": [1],
                "characters": ["陈汉升"],
                "worldbuilding_entities": ["organization_x"],
            },
            "limitations": [],
            "confidence": 0.8,
        },
        material_id="nm_demo",
        title="示例",
    )

    assert profile.material_id == "nm_demo"
    assert profile.title == "示例"
    assert profile.evidence_index.chapters == (1,)
    assert profile.evidence_index.characters == ("陈汉升",)
    assert profile.evidence_index.worldbuilding_entities == ("organization_x",)


def test_normalize_work_profile_rejects_empty_evidence() -> None:
    with pytest.raises(ValueError, match="evidence_index"):
        normalize_work_profile_response(
            {
                "core_hooks": ["钩子"],
                "reader_expectations": [],
                "story_structure": {},
                "character_dynamics": {},
                "worldbuilding_drivers": [],
                "motifs_and_techniques": [],
                "transferable_lessons": [],
                "evidence_index": {
                    "chapters": [],
                    "characters": [],
                    "worldbuilding_entities": [],
                },
            },
            material_id="nm_demo",
            title="示例",
        )


def test_work_profile_prompt_requires_lower_level_evidence() -> None:
    system_prompt, user_prompt = build_work_profile_prompt(
        {
            "material_id": "nm_demo",
            "title": "示例",
            "facts": {
                "chapters": [{"chapter": 1, "summary": "商业竞争开端"}],
                "characters": [{"name": "陈汉升", "role": "protagonist"}],
                "worldbuilding_entities": [
                    {"id": "organization_x", "name": "创业公司"}
                ],
            },
        }
    )

    assert "work_profile.yaml 不是事实来源" in system_prompt
    assert "evidence_index" in system_prompt
    assert "chapters.yaml" in system_prompt
    assert "characters/profiles" in system_prompt
    assert "worldbuilding/" in system_prompt
    assert "nm_demo" in user_prompt
    assert "商业竞争开端" in user_prompt
