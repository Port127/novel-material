from novel_material.pipeline.analyze_validators import (
    normalize_chapter_analysis_response,
)
from novel_material.pipeline.release_gate import evaluate_release_gate
from novel_material.runtime.contracts import RunStatus, StageResult


def stage(name: str, status: RunStatus, *, outputs=None):
    return StageResult(
        stage_id=f"stage-{name}",
        name=name,
        status=status,
        outputs=outputs or {},
    )


def test_18cb_like_degraded_artifacts_do_not_sync_by_default() -> None:
    result = evaluate_release_gate(
        "nm_fixture_18cb",
        (
            stage("analyze", RunStatus.SUCCESS),
            stage(
                "worldbuilding",
                RunStatus.DEGRADED,
                outputs={"llm_success": False, "entity_count": 0},
            ),
            stage(
                "characters",
                RunStatus.DEGRADED,
                outputs={
                    "biography_target_count": 12,
                    "biography_completed_count": 0,
                },
            ),
            stage("profile", RunStatus.FAILED),
            stage(
                "audit",
                RunStatus.DEGRADED,
                outputs={"summary": {"error": 1, "blocker": 0}},
            ),
        ),
        mode="standard",
        allow_degraded_sync=False,
    )

    assert result.outputs["decision"] == "block"
    assert result.status is RunStatus.FAILED


def test_7u96_like_pacing_null_is_warning_quality_fallback() -> None:
    result = normalize_chapter_analysis_response(
        {
            "summary": "这一章完成一次冲突升级，主角被迫正面应对敌人。",
            "pacing": None,
            "key_event": "主角在冲突中明确反击路线。",
            "hook_type": "危机",
            "characters_appear": ["主角"],
            "chapter_functions": ["战斗冲突"],
            "setting": ["擂台"],
            "emotional_tone": ["紧张"],
            "scene_type": ["战斗"],
            "technique": ["悬念"],
            "tension_level": 5,
        }
    )

    assert result["pacing"] == "快"
    assert result["quality"]["fallback_fields"] == ["pacing"]
