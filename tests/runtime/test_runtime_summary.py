"""运行事件汇总测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from novel_material.runtime.contracts import RunStatus
from novel_material.runtime.summary import RunSummaryAccumulator
from novel_material.runtime.testing import event


def test_summary_aggregates_tokens_diagnostics_and_latest_stage_counts():
    summary = RunSummaryAccumulator()
    summary.consume(
        event(
            "ProgressUpdated",
            stage_id="stage-1",
            attributes={
                "counts": {
                    "expected": 10,
                    "processed": 4,
                    "succeeded": 3,
                    "degraded": 1,
                    "failed": 0,
                    "remaining": 6,
                }
            },
        )
    )
    summary.consume(
        event(
            "OperationCompleted",
            attributes={
                "input_tokens": 100,
                "output_tokens": 20,
                "reasoning_tokens_observed": 5,
                "total_tokens": 125,
            },
        )
    )
    summary.consume(
        event(
            "DiagnosticRaised",
            attributes={"diagnostic_code": "schema_invalid", "count": 2},
        )
    )

    snapshot = summary.snapshot()

    assert snapshot.stage_counts["stage-1"].processed == 4
    assert snapshot.input_tokens == 100
    assert snapshot.output_tokens == 20
    assert snapshot.reasoning_tokens == 5
    assert snapshot.total_tokens == 125
    assert snapshot.diagnostic_counts == {"schema_invalid": 2}


def test_summary_ignores_duplicate_event_id():
    summary = RunSummaryAccumulator()
    completed = event(
        "OperationCompleted",
        event_id="event-fixed",
        attributes={"total_tokens": 10},
    )

    summary.consume(completed)
    summary.consume(completed)

    assert summary.snapshot().total_tokens == 10


def test_summary_aggregates_run_operations_cost_and_named_stages():
    summary = RunSummaryAccumulator()
    started_at = datetime(2026, 6, 23, 1, tzinfo=timezone.utc)
    completed_at = started_at + timedelta(seconds=5)
    counts = {
        "expected": 1,
        "processed": 1,
        "succeeded": 1,
        "degraded": 0,
        "failed": 0,
        "remaining": 0,
    }

    summary.consume(event("RunStarted", occurred_at=started_at))
    summary.consume(event("OperationStarted"))
    summary.consume(
        event(
            "OperationCompleted",
            attributes={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "estimated_cost": 0.25,
            },
        )
    )
    summary.consume(
        event(
            "ProgressUpdated",
            stage_id="stage-1",
            attributes={
                "counts": {
                    **counts,
                    "processed": 0,
                    "succeeded": 0,
                    "remaining": 1,
                }
            },
        )
    )
    summary.consume(
        event(
            "StageCompleted",
            stage_id="stage-1",
            status=RunStatus.SUCCESS,
            duration_ms=1250,
            attributes={"stage_name": "analyze", "counts": counts},
        )
    )
    summary.consume(event("RunCompleted", occurred_at=completed_at))

    snapshot = summary.snapshot()

    assert snapshot.started_at == started_at
    assert snapshot.completed_at == completed_at
    assert snapshot.operation_attempts == 1
    assert snapshot.operation_completed == 1
    assert snapshot.estimated_cost == 0.25
    assert set(snapshot.stage_counts) == {"analyze"}
    assert snapshot.stage_counts["analyze"].processed == 1
    assert snapshot.stage_durations_ms == {"analyze": 1250}
    assert snapshot.stage_statuses == {"analyze": RunStatus.SUCCESS}


def test_summary_marks_total_cost_unavailable_when_any_call_has_no_cost():
    summary = RunSummaryAccumulator()
    summary.consume(
        event("OperationCompleted", attributes={"estimated_cost": 0.25})
    )
    summary.consume(
        event("OperationCompleted", attributes={"estimated_cost": None})
    )

    snapshot = summary.snapshot()

    assert snapshot.operation_completed == 2
    assert snapshot.estimated_cost is None
