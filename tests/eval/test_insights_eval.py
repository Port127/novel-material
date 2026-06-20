"""chapter_insights 确定性评估测试。"""

from novel_material.eval.insights_eval import score_insight_case


def test_score_insight_case_calculates_core_metrics():
    case = {
        "expected_profiles": ["common", "xuanhuan"],
        "expected_fields": {
            "common": {
                "conflict_contains": ["羞辱", "压制"],
                "reader_hook_contains": ["戒指"],
            },
            "genre": {
                "resource_gain_contains": ["戒指", "传承"],
            },
        },
    }
    insight = {
        "profiles": ["common", "xuanhuan"],
        "common": {
            "conflict": "家族羞辱和压制推动主角反击。",
            "reader_hook": "戒指是否藏有传承。",
            "writing_takeaway": "先压低处境，再给出具体机缘。",
        },
        "genre": {
            "resource_gain": "获得戒指传承线索。",
        },
        "evidence": [{"field": "resource_gain", "source": "chapter_summary", "text": "戒指出现异常。"}],
        "quality": {"repaired": False, "validation_errors": []},
    }

    metrics = score_insight_case(case, insight)

    assert metrics["field_presence_rate"] == 1.0
    assert metrics["keyword_hit_rate"] == 1.0
    assert metrics["evidence_presence_rate"] == 1.0
    assert metrics["profile_resolution_accuracy"] == 1.0
    assert metrics["repair_rate"] == 0.0
    assert metrics["invalid_after_repair_rate"] == 0.0
    assert metrics["generic_phrase_rate"] == 0.0
