"""统一运行事件与结果契约测试。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from novel_material.runtime.contracts import (
    Diagnostic,
    ExitCode,
    ProgressCounts,
    RunEvent,
    RunResult,
    RunStatus,
    StageResult,
    aggregate_status,
)


def test_progress_counts_reject_inconsistent_outcome_total():
    with pytest.raises(ValidationError, match="结果计数不能大于 processed"):
        ProgressCounts(
            expected=10,
            processed=8,
            succeeded=7,
            failed=2,
            remaining=2,
        )


def test_progress_counts_reject_inconsistent_remaining():
    with pytest.raises(ValidationError, match="remaining 必须等于"):
        ProgressCounts(expected=10, processed=8, succeeded=8, remaining=1)


def test_degraded_run_maps_to_exit_code_three():
    stage = StageResult(
        stage_id="stage-1",
        name="insights",
        status=RunStatus.DEGRADED,
        counts=ProgressCounts(
            expected=10,
            processed=10,
            succeeded=9,
            degraded=1,
        ),
    )

    result = RunResult.from_stages(
        run_id="run-1",
        command="pipeline insights",
        stages=[stage],
    )

    assert result.status is RunStatus.DEGRADED
    assert result.exit_code is ExitCode.DEGRADED
    assert result.counts.degraded == 1


def test_blocking_failure_preserves_unprocessed_stage_count():
    failed = StageResult(
        stage_id="stage-1",
        name="analyze",
        status=RunStatus.FAILED,
        diagnostics=(
            Diagnostic(
                code="analysis_failed",
                message="分析失败",
                severity="error",
            ),
        ),
    )

    result = RunResult.from_stages(
        run_id="run-1",
        command="pipeline full",
        stages=[failed],
        expected_stages=3,
    )

    assert result.status is RunStatus.FAILED
    assert result.exit_code is ExitCode.FAILED
    assert result.counts.processed == 1
    assert result.counts.remaining == 2
    assert result.diagnostics[0].code == "analysis_failed"


def test_stage_result_can_carry_ingest_material_id():
    stage = StageResult(
        stage_id="stage-1",
        name="ingest",
        status=RunStatus.SUCCESS,
        outputs={"material_id": "nm_demo"},
    )

    assert stage.outputs["material_id"] == "nm_demo"


def test_empty_stage_collection_is_successful():
    result = RunResult.from_stages(
        run_id="run-1",
        command="storage sync --all",
        stages=[],
    )

    assert result.status is RunStatus.SUCCESS
    assert result.exit_code is ExitCode.SUCCESS
    assert result.counts.expected == 0


def test_status_aggregation_uses_fixed_priority():
    assert aggregate_status([RunStatus.SUCCESS, RunStatus.DEGRADED]) is RunStatus.DEGRADED
    assert aggregate_status([RunStatus.INTERRUPTED, RunStatus.FAILED]) is RunStatus.FAILED


def test_run_event_is_immutable_and_keeps_request_ids_separate():
    now = datetime.now(timezone.utc)
    event = RunEvent(
        event_name="OperationCompleted",
        event_id="event-1",
        occurred_at=now,
        observed_at=now,
        run_id="run-1",
        request_id="req-internal",
        provider_request_id="chatcmpl-provider",
        command="pipeline analyze",
        component="llm",
        operation="request",
    )

    assert event.request_id == "req-internal"
    assert event.provider_request_id == "chatcmpl-provider"
    with pytest.raises(ValidationError):
        event.status = RunStatus.SUCCESS


def test_run_event_rejects_naive_timestamps():
    naive = datetime.now()
    with pytest.raises(ValidationError, match="时区"):
        RunEvent(
            event_name="RunStarted",
            event_id="event-1",
            occurred_at=naive,
            observed_at=naive,
            run_id="run-1",
            command="pipeline analyze",
            component="pipeline",
            operation="analyze",
        )
