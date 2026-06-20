"""chapter_insights 校验测试。"""

from novel_material.analysis_profiles import load_profiles, merge_profiles
from novel_material.validation.insights import validate_insight


def test_valid_insight_passes():
    profile = merge_profiles(load_profiles(["common", "xuanhuan"]))
    insight = {
        "schema_version": "1.0",
        "common": {
            "core_event": "主角被家族羞辱并发现戒指异常。",
            "scene_goal": "主角想保住尊严并弄清戒指来历。",
            "conflict": "家族压迫与隐藏机缘之间形成冲突。",
            "stakes": "失败会失去修炼资源和身份。",
            "turning_point": "戒指回应血液，暗示传承。",
            "reader_hook": "戒指传承是否能改变命运。",
            "character_change": "主角从被动受辱转向主动寻找机会。",
            "writing_takeaway": "先压低处境，再给出可验证但未揭开的机缘。",
        },
        "genre": {
            "power_progression": "没有突破，但建立修炼受阻背景。",
            "resource_gain": "获得戒指传承线索。",
            "face_slapping": "铺垫后续对家族的反击。",
        },
        "evidence": [
            {"field": "core_event", "source": "chapter_summary", "text": "主角被逐出家族，戒指出现异常。"},
            {"field": "resource_gain", "source": "chapter_summary", "text": "戒指出现异常，提示传承线索。"},
        ],
        "confidence": 0.8,
    }
    assert validate_insight(insight, profile) == []


def test_missing_required_field_fails():
    profile = merge_profiles(load_profiles(["common"]))
    insight = {"schema_version": "1.0", "common": {}, "genre": {}, "evidence": [], "confidence": 0.8}
    errors = validate_insight(insight, profile)
    assert any("core_event" in error for error in errors)
    assert any("evidence" in error for error in errors)
