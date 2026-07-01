from novel_material.pipeline.release_gate import evaluate_release_gate
from novel_material.runtime.contracts import RunStatus, StageResult


def stage(name: str, status: RunStatus, *, outputs=None, diagnostics=()):
    return StageResult(
        stage_id=f"stage-{name}",
        name=name,
        status=status,
        outputs=outputs or {},
        diagnostics=diagnostics,
    )


def test_audit_error_blocks_sync() -> None:
    result = evaluate_release_gate(
        "nm_demo",
        (
            stage("analyze", RunStatus.SUCCESS),
            stage(
                "audit",
                RunStatus.DEGRADED,
                outputs={"summary": {"error": 1, "blocker": 0}},
            ),
        ),
        mode="standard",
        allow_degraded_sync=False,
    )

    assert result.status is RunStatus.FAILED
    assert result.outputs["decision"] == "block"
    assert result.outputs["release_status"] == "failed"
    assert "audit_error" in result.outputs["reasons"]


def test_degraded_hold_can_be_overridden() -> None:
    result = evaluate_release_gate(
        "nm_demo",
        (
            stage("analyze", RunStatus.SUCCESS),
            stage("worldbuilding", RunStatus.DEGRADED),
            stage("profile", RunStatus.SUCCESS),
            stage("audit", RunStatus.SUCCESS),
        ),
        mode="standard",
        allow_degraded_sync=True,
    )

    assert result.status is RunStatus.SUCCESS
    assert result.outputs["decision"] == "allow"
    assert result.outputs["release_status"] == "degraded"
    assert result.outputs["override"] is True


def test_failed_stage_cannot_be_overridden() -> None:
    result = evaluate_release_gate(
        "nm_demo",
        (
            stage("analyze", RunStatus.FAILED),
            stage("audit", RunStatus.SUCCESS),
        ),
        mode="standard",
        allow_degraded_sync=True,
    )

    assert result.status is RunStatus.FAILED
    assert result.outputs["decision"] == "block"
    assert result.outputs["override"] is False


def test_profile_missing_blocks_standard() -> None:
    result = evaluate_release_gate(
        "nm_demo",
        (
            stage("analyze", RunStatus.SUCCESS),
            stage("audit", RunStatus.SUCCESS),
        ),
        mode="standard",
        allow_degraded_sync=False,
    )

    assert result.status is RunStatus.FAILED
    assert result.outputs["decision"] == "block"
    assert "profile_missing" in result.outputs["reasons"]
