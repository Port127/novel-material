"""PipelineOrchestrator 结果与故障语义测试。"""

from __future__ import annotations

import pytest

from novel_material.pipeline.orchestrator import (
    PipelineOrchestrator,
    RunRequest,
    StageContractError,
    StageSpec,
)
from novel_material.runtime.contracts import RunStatus, StageResult
from novel_material.runtime.dispatcher import RuntimeDispatcher, SinkCriticality
from novel_material.runtime.testing import MemoryEventSink


def stage(name: str, status: RunStatus) -> StageResult:
    return StageResult(stage_id=f"stage-{name}", name=name, status=status)


def spec(name: str, status: RunStatus, *, blocking: bool = False) -> StageSpec:
    return StageSpec(name=name, execute=lambda _request: stage(name, status), blocking=blocking)


def request() -> RunRequest:
    return RunRequest(run_id="run-1", command="pipeline full", material_id="nm_demo")


def test_orchestrator_keeps_processing_allowed_failures_until_blocking_failure():
    orchestrator = PipelineOrchestrator(
        [
            spec("analyze", RunStatus.DEGRADED),
            spec("outline", RunStatus.SUCCESS),
            spec("sync", RunStatus.FAILED, blocking=True),
            spec("after-sync", RunStatus.SUCCESS),
        ]
    )

    result = orchestrator.run(request())

    assert [item.name for item in result.stages] == ["analyze", "outline", "sync"]
    assert result.status is RunStatus.FAILED
    assert result.exit_code == 1
    assert result.counts.remaining == 1


class FailingSink:
    def __init__(self, criticality: SinkCriticality):
        self.name = criticality.value
        self.criticality = criticality

    def emit(self, _event):
        raise OSError("sink failed")


def test_required_sink_failure_degrades_successful_run():
    healthy = MemoryEventSink()
    orchestrator = PipelineOrchestrator(
        [spec("analyze", RunStatus.SUCCESS)],
        dispatcher=RuntimeDispatcher(
            [FailingSink(SinkCriticality.REQUIRED), healthy]
        ),
    )

    result = orchestrator.run(request())

    assert result.status is RunStatus.DEGRADED
    assert result.exit_code == 3
    assert result.diagnostics[0].code == "event_sink_failed"
    assert healthy.events_named("RunStarted")


def test_best_effort_sink_failure_does_not_change_business_result():
    orchestrator = PipelineOrchestrator(
        [spec("analyze", RunStatus.SUCCESS)],
        dispatcher=RuntimeDispatcher([FailingSink(SinkCriticality.BEST_EFFORT)]),
    )

    result = orchestrator.run(request())

    assert result.status is RunStatus.SUCCESS
    assert result.exit_code == 0


def test_orchestrator_rejects_non_stage_result():
    bad = StageSpec(name="bad", execute=lambda _request: True, blocking=True)

    with pytest.raises(StageContractError):
        PipelineOrchestrator([bad]).run(request())
