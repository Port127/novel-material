from novel_material.pipeline.characters_core import _characters_stage_status
from novel_material.pipeline.characters_quality import build_character_quality_counts
from novel_material.runtime.contracts import RunStatus


def test_all_biography_targets_failed_is_degraded() -> None:
    status, diagnostic = _characters_stage_status(
        biography_target_count=12,
        biography_completed_count=0,
        biography_failed_count=12,
        fallback_count=12,
    )

    assert status is RunStatus.DEGRADED
    assert diagnostic.code == "character_biography_all_failed"


def test_no_biography_target_can_succeed() -> None:
    status, diagnostic = _characters_stage_status(
        biography_target_count=0,
        biography_completed_count=0,
        biography_failed_count=0,
        fallback_count=0,
    )

    assert status is RunStatus.SUCCESS
    assert diagnostic is None


def test_build_character_quality_counts_used_for_stage_outputs():
    profiles = [
        {"name": "甲", "profile_level": "full"},
        {"name": "乙", "profile_level": "enriched"},
        {"name": "丙", "profile_level": "partial"},
        {"name": "丁", "profile_level": "fallback"},
    ]

    assert build_character_quality_counts(profiles) == {
        "full": 1,
        "enriched": 1,
        "partial": 1,
        "fallback": 1,
    }
