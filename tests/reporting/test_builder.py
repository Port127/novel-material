from datetime import datetime, timedelta, timezone

import pytest

from novel_material.reporting.builder import ReportBuildError, build_run_report
from novel_material.reporting.models import PipelineRunReport
from novel_material.runtime.contracts import RunStatus
from novel_material.runtime.testing import event


def audit_payload() -> dict:
    return {
        "schema_version": 1,
        "material_id": "nm_demo",
        "checks": ["characters"],
        "character_quality": {
            "biography_target_count": 5,
            "biography_completed_count": 4,
            "brief_profile_count": 3,
            "biography_failed_count": 1,
        },
        "worldbuilding_quality": {
            "layout": "layered",
            "entity_count": 8,
            "relation_count": 6,
            "evidence_count": 21,
            "broken_relation_count": 1,
            "missing_evidence_count": 2,
        },
        "issues": [
            {
                "code": "character_profile_fallback",
                "severity": "error",
                "artifact": "characters/profiles/主角.yaml",
                "message": "主要人物为空壳",
                "evidence": {},
                "next_actions": [
                    "nm pipeline characters nm_demo --repair-character 主角"
                ],
                "reviewable": False,
                "review_state": "not_required",
            }
        ],
    }


def run_events(*, include_audit: bool = True):
    started = datetime(2026, 6, 23, 1, 0, tzinfo=timezone.utc)
    events = [
        event(
            "RunStarted",
            occurred_at=started,
            material_id="nm_demo",
            command="pipeline full",
        ),
        event(
            "StageCompleted",
            occurred_at=started + timedelta(seconds=10),
            stage_id="stage-audit",
            material_id="nm_demo",
            command="pipeline full",
            status="degraded",
            duration_ms=10000,
            attributes={
                "stage_name": "audit",
                "counts": {},
                "diagnostics": [],
            },
        ),
        event(
            "OperationStarted",
            occurred_at=started + timedelta(seconds=10),
            material_id="nm_demo",
            command="pipeline full",
        ),
        event(
            "OperationCompleted",
            occurred_at=started + timedelta(seconds=11),
            material_id="nm_demo",
            command="pipeline full",
            attributes={
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "estimated_cost": 0.02,
            },
        ),
        event(
            "RunCompleted",
            occurred_at=started + timedelta(seconds=20),
            material_id="nm_demo",
            command="pipeline full",
            status="degraded",
            attributes={"counts": {}, "diagnostics": []},
        ),
    ]
    if include_audit:
        events.insert(
            2,
            event(
                "ArtifactAuditCompleted",
                occurred_at=started + timedelta(seconds=10),
                stage_id="stage-audit",
                material_id="nm_demo",
                command="pipeline full",
                status="degraded",
                attributes={"audit": audit_payload()},
            ),
        )
    return events


def test_builder_combines_runtime_and_artifact_quality() -> None:
    report = build_run_report(run_events())

    assert report.run_id == "run-test"
    assert report.material_id == "nm_demo"
    assert report.status is RunStatus.DEGRADED
    assert report.duration_ms == 20000
    assert report.runtime.operation_attempts == 1
    assert report.runtime.operation_completed == 1
    assert report.runtime.total_tokens == 150
    assert report.runtime.estimated_cost == 0.02
    assert report.artifact_quality.summary.error == 1
    assert report.artifact_quality.character_quality.biography_target_count == 5
    assert report.artifact_quality.character_quality.biography_completed_count == 4
    assert report.artifact_quality.character_quality.brief_profile_count == 3
    assert report.artifact_quality.character_quality.biography_failed_count == 1
    assert report.artifact_quality.worldbuilding_quality.layout == "layered"
    assert report.artifact_quality.worldbuilding_quality.entity_count == 8
    assert report.artifact_quality.worldbuilding_quality.relation_count == 6
    assert report.artifact_quality.worldbuilding_quality.evidence_count == 21
    assert report.artifact_quality.worldbuilding_quality.broken_relation_count == 1
    assert report.artifact_quality.worldbuilding_quality.missing_evidence_count == 2
    assert report.next_actions == (
        "nm pipeline characters nm_demo --repair-character 主角",
    )


def test_builder_rejects_missing_run_boundaries() -> None:
    with pytest.raises(ReportBuildError, match="RunStarted"):
        build_run_report([])

    with pytest.raises(ReportBuildError, match="RunCompleted"):
        build_run_report([run_events()[0]])


def test_builder_rejects_events_from_multiple_runs() -> None:
    events = run_events()
    events.append(
        event(
            "DiagnosticRaised",
            run_id="run-other",
            attributes={"diagnostic_code": "foreign"},
        )
    )

    with pytest.raises(ReportBuildError, match="run_id"):
        build_run_report(events)


def test_builder_combines_prior_and_current_stages_without_domain_outputs() -> None:
    events = run_events()
    started = events[0]
    events[0] = started.model_copy(
        update={
            "attributes": {
                "report_prior_stages": [
                    {
                        "name": "ingest",
                        "status": "success",
                        "duration_ms": 250,
                        "counts": {},
                        "diagnostics": [],
                    }
                ]
            }
        }
    )

    report = build_run_report(events)

    assert [stage.name for stage in report.stages] == ["ingest", "audit"]
    assert report.stages[0].duration_ms == 250


def test_builder_marks_missing_audit_without_failing_report() -> None:
    report = build_run_report(run_events(include_audit=False))

    assert report.artifact_quality.issues == ()
    assert report.runtime.diagnostic_counts["audit_missing"] == 1


def test_builder_extracts_release_gate_summary() -> None:
    events = run_events()
    started = events[0].occurred_at
    events.insert(
        -1,
        event(
            "StageCompleted",
            occurred_at=started + timedelta(seconds=12),
            stage_id="stage-release",
            material_id="nm_demo",
            command="pipeline full",
            status="degraded",
            duration_ms=12,
            attributes={
                "stage_name": "release_gate",
                "counts": {},
                "diagnostics": [{"code": "release_gate_held"}],
                "outputs": {
                    "decision": "hold",
                    "release_status": "degraded",
                    "allow_degraded_sync": False,
                    "override": False,
                    "reasons": ["worldbuilding_degraded"],
                },
            },
        ),
    )

    report = build_run_report(events)

    assert report.release_gate.decision == "hold"
    assert report.release_gate.release_status == "degraded"
    assert report.release_gate.reasons == ("worldbuilding_degraded",)


def test_builder_rejects_stage_completed_without_status() -> None:
    events = run_events()
    stage_index = next(
        index
        for index, item in enumerate(events)
        if item.event_name == "StageCompleted"
    )
    events[stage_index] = events[stage_index].model_copy(update={"status": None})

    with pytest.raises(ReportBuildError, match="StageCompleted.*status"):
        build_run_report(events)


def test_builder_wraps_invalid_event_counts_as_report_error() -> None:
    events = run_events()
    completed_index = next(
        index
        for index, item in enumerate(events)
        if item.event_name == "RunCompleted"
    )
    events[completed_index] = events[completed_index].model_copy(
        update={"attributes": {"counts": {"expected": -1}}}
    )

    with pytest.raises(ReportBuildError, match="RunCompleted.*counts"):
        build_run_report(events)


def history_report(
    *,
    run_id: str,
    duration_ms: float,
    completed_at: datetime,
    status: RunStatus = RunStatus.SUCCESS,
    material_id: str = "nm_demo",
    command: str = "pipeline full",
) -> PipelineRunReport:
    return PipelineRunReport(
        run_id=run_id,
        material_id=material_id,
        command=command,
        status=status,
        started_at=completed_at - timedelta(milliseconds=duration_ms),
        completed_at=completed_at,
        duration_ms=duration_ms,
    )


def test_builder_uses_recent_three_comparable_successes_for_baseline() -> None:
    now = datetime(2026, 6, 23, 2, tzinfo=timezone.utc)
    history = (
        history_report(
            run_id="old",
            duration_ms=10000,
            completed_at=now - timedelta(hours=4),
        ),
        history_report(
            run_id="one",
            duration_ms=20000,
            completed_at=now - timedelta(hours=3),
        ),
        history_report(
            run_id="two",
            duration_ms=30000,
            completed_at=now - timedelta(hours=2),
        ),
        history_report(
            run_id="three",
            duration_ms=40000,
            completed_at=now - timedelta(hours=1),
        ),
        history_report(
            run_id="failed",
            duration_ms=99999,
            completed_at=now,
            status=RunStatus.FAILED,
        ),
        history_report(
            run_id="other-material",
            duration_ms=99999,
            completed_at=now,
            material_id="nm_other",
        ),
    )

    report = build_run_report(run_events(), baseline_reports=history)

    assert report.baseline.kind == "same_material_command"
    assert report.baseline.baseline_duration_ms == 30000
    assert report.baseline.delta_percent == pytest.approx(-33.3333333333)
