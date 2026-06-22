"""运行事件汇总测试。"""

from __future__ import annotations

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
