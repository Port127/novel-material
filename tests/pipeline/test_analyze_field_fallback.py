import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.analyze_validators import (
    normalize_chapter_analysis_response,
)


def base_payload(**overrides):
    payload = {
        "summary": "主角遇到强敌并被迫改变计划。",
        "pacing": "中",
        "key_event": "主角决定主动反击。",
        "hook_type": "危机",
        "characters_appear": ["主角"],
        "chapter_functions": ["战斗冲突"],
        "setting": ["城门"],
        "emotional_tone": ["紧张"],
        "scene_type": ["战斗"],
        "technique": ["悬念"],
        "tension_level": 5,
    }
    payload.update(overrides)
    return payload


def test_pacing_none_is_recovered_with_quality_marker() -> None:
    result = normalize_chapter_analysis_response(base_payload(pacing=None))

    assert result["pacing"] == "快"
    assert result["quality"]["fallback_fields"] == ["pacing"]
    assert "pacing" in result["quality"]["fallback_reason"]


def test_hard_fact_missing_still_fails() -> None:
    with pytest.raises(LLMResponseContractError):
        normalize_chapter_analysis_response(base_payload(summary=None))
