import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.material.classify import parse_classification_result
from novel_material.pipeline.analyze_validators import normalize_chapter_analysis_response
from novel_material.pipeline.outline_logic import normalize_premise_response
from novel_material.pipeline.tags import default_tags_response, normalize_tags_response
from novel_material.pipeline.worldbuilding import normalize_worldbuilding_response
from novel_material.pipeline.evaluate import normalize_evaluation_response
from novel_material.pipeline.outline_acts import normalize_acts_response
from novel_material.pipeline.outline_beats import normalize_beats_response
from novel_material.pipeline.characters_layer import normalize_characters_response


def test_worldbuilding_normalizes_empty_object_dimensions():
    assert normalize_worldbuilding_response({
        "power_system": [], "geography": None, "factions": None, "lore": {},
    }) == {"power_system": {}, "geography": {}, "factions": [], "lore": {}}


def test_worldbuilding_rejects_non_empty_object_list():
    with pytest.raises(LLMResponseContractError, match="power_system"):
        normalize_worldbuilding_response({"power_system": [{"name": "修炼"}]})


def _chapter_payload():
    return {
        "summary": "足够长的章节摘要", "characters_appear": ["甲"],
        "chapter_functions": ["人物亮相"], "tension_level": 3, "pacing": "中",
        "setting": ["办公室"], "key_event": "甲作出决定", "emotional_tone": ["紧张"],
        "scene_type": ["对话"], "technique": [], "hook_type": "无钩子",
    }


@pytest.mark.parametrize("field,value", [
    ("summary", []), ("characters_appear", "甲"), ("tension_level", "3"),
])
def test_chapter_response_rejects_wrong_types(field, value):
    payload = _chapter_payload()
    payload[field] = value
    with pytest.raises(LLMResponseContractError, match=field):
        normalize_chapter_analysis_response(payload)


def test_premise_rejects_string_theme():
    with pytest.raises(LLMResponseContractError, match="theme"):
        normalize_premise_response({
            "premise": "主角崛起", "structure_type": "三幕式", "total_acts": 3,
            "theme": "成长", "tone": [],
        })


def test_tags_reject_wrong_collection_before_storage():
    payload = default_tags_response("都市")
    payload["hooks"] = 1
    with pytest.raises(LLMResponseContractError, match="hooks"):
        normalize_tags_response(payload)


def test_classification_rejects_quality_list():
    with pytest.raises(LLMResponseContractError, match="classification.quality"):
        parse_classification_result({"genre_primary": "其他", "quality": []}, (["其他"], {}))


def test_evaluation_rejects_string_character_candidates():
    with pytest.raises(LLMResponseContractError, match="core_character_candidates"):
        normalize_evaluation_response({
            "novel_type": ["都市"],
            "premise": "主角重新选择人生",
            "main_thread_summary": "主线",
            "stage_map": [],
            "core_character_candidates": "王某",
            "worldbuilding_dimensions": [],
            "analysis_focus": [],
        })


def test_acts_accept_wrapped_list_and_reject_bad_sequence():
    acts = [{
        "act_number": 1, "name": "第一幕", "chapter_start": 1, "chapter_end": 10,
        "sequences": [{"sequence_number": 1, "title": "开篇", "chapter_start": 1,
                       "chapter_end": 10, "description": "建立故事"}],
    }]
    assert normalize_acts_response({"acts": acts}, 10) == acts
    acts[0]["sequences"] = ["开篇"]
    with pytest.raises(LLMResponseContractError, match="sequences"):
        normalize_acts_response(acts, 10)


def test_beats_reject_out_of_range_tension():
    with pytest.raises(LLMResponseContractError, match="tension"):
        normalize_beats_response([{
            "beat_number": 1, "title": "转折", "chapter": 5,
            "description": "发生转折", "tension": 6,
        }], 1, 10)


def test_characters_reject_unknown_candidate_and_bad_relationships():
    with pytest.raises(LLMResponseContractError, match="候选名单"):
        normalize_characters_response([{"name": "乙"}], {"甲"})
    with pytest.raises(LLMResponseContractError, match="relationships"):
        normalize_characters_response([{"name": "甲", "relationships": ["朋友"]}], {"甲"})
