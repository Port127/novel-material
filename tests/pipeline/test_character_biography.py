"""主要人物完整小传响应契约测试。"""

import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.characters_biography import normalize_biography_response


def _full_profile() -> dict:
    return {
        "name": "陈汉升",
        "role": "protagonist",
        "archetype": "重生创业者",
        "moral_spectrum": "灰色",
        "identity": "学生与创业者",
        "life_summary": "重生后重新处理事业和关系。",
        "external_goal": "抓住商业机会。",
        "internal_need": "理解亲密关系中的责任。",
        "fear": "重蹈覆辙。",
        "fatal_flaw": "自负且逃避承诺。",
        "contradiction": "精明外壳下仍有情感软肋。",
        "arc_stages": [
            {
                "stage": "opening",
                "change": "主动破局",
                "evidence": {"chapters": [1]},
            }
        ],
        "relationships": [
            {
                "character": "沈幼楚",
                "dynamic": "守护与亏欠",
                "evidence": {"chapters": [2]},
            }
        ],
        "habits": ["嘴硬"],
        "speech_style": "玩世不恭",
        "interaction_patterns": ["以调侃化解压力"],
        "key_scenes": [
            {"chapter": 1, "event": "重生醒来", "function": "确立新选择"}
        ],
        "craft_notes": [{"technique": "反差塑造", "boundary": "不可直接照搬人设"}],
        "confidence": 0.86,
        "basis": "inference",
        "description": "核心人物完整小传。",
        "arc_summary": "从重生后的功利选择走向承担关系代价。",
        "psychology": {"motivation": "改变命运"},
        "narrative_function": "推动主线",
        "first_appearance_chapter": 1,
        "key_events": [{"chapter": 1, "description": "重生"}],
    }


def test_normalize_biography_response_requires_full_profile_fields():
    result = normalize_biography_response(
        {"characters": [_full_profile()]},
        candidate_names={"陈汉升"},
    )

    profile = result[0]
    assert profile["profile_level"] == "full"
    assert profile["biography_complete"] is True
    assert profile["basis"] == "inference"
    assert profile["relationships"][0]["relationship"] == "守护与亏欠"


def test_biography_response_rejects_missing_psychology_and_arc():
    with pytest.raises(LLMResponseContractError, match="arc_stages"):
        normalize_biography_response(
            {"characters": [{"name": "陈汉升", "role": "protagonist"}]},
            candidate_names={"陈汉升"},
        )


def test_biography_response_rejects_invalid_basis():
    payload = _full_profile()
    payload["basis"] = "guess"

    with pytest.raises(LLMResponseContractError, match="basis"):
        normalize_biography_response(
            {"characters": [payload]},
            candidate_names={"陈汉升"},
        )
