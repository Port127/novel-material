"""PipelineOrchestrator 结果与故障语义测试。"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from novel_material.pipeline.orchestrator import (
    PipelineOrchestrator,
    RunRequest,
    StageContractError,
    StageSpec,
    render_next_actions,
)
from novel_material.runtime.contracts import RunStatus, StageResult
from novel_material.runtime.dispatcher import RuntimeDispatcher, SinkCriticality
from novel_material.runtime.testing import MemoryEventSink
from novel_material.pipeline.state import PipelineStateStore


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


def test_continue_plan_starts_from_invalid_insights_and_includes_downstream():
    names = (
        "analyze", "outline", "worldbuilding", "characters", "tags",
        "insights", "refine", "sync",
    )
    stages = {
        name: stage(
            name,
            RunStatus.DEGRADED if name == "insights" else RunStatus.SUCCESS,
        )
        for name in names
    }
    inspection = SimpleNamespace(exists=True, stages=stages)

    plan = PipelineOrchestrator.plan_continue(inspection)

    assert plan.first_stage == "insights"
    assert plan.stage_names == ("insights", "refine", "sync")


def test_orchestrator_persists_latest_stage_result(tmp_path):
    store = PipelineStateStore(tmp_path)
    orchestrator = PipelineOrchestrator(
        [spec("analyze", RunStatus.SUCCESS)],
        state_store=store,
    )

    result = orchestrator.run(request())
    persisted = store.read_latest()

    assert result.status is RunStatus.SUCCESS
    assert persisted.status is RunStatus.SUCCESS
    assert persisted.generation >= 2
    assert [item.name for item in persisted.stages] == ["analyze"]


def test_orchestrator_converts_keyboard_interrupt_to_run_result(tmp_path):
    store = PipelineStateStore(tmp_path)
    interrupted = StageSpec(
        name="analyze",
        execute=lambda _request: (_ for _ in ()).throw(KeyboardInterrupt()),
        blocking=True,
    )

    result = PipelineOrchestrator([interrupted], state_store=store).run(request())

    assert result.status is RunStatus.INTERRUPTED
    assert result.exit_code == 130
    assert result.stages[0].diagnostics[0].code == "user_interrupted"
    assert store.read_latest().status is RunStatus.INTERRUPTED


def test_next_actions_render_real_material_id():
    result = PipelineOrchestrator(
        [spec("analyze", RunStatus.FAILED, blocking=True)]
    ).run(request())

    actions = render_next_actions(result, "nm_demo")

    assert actions == (
        "python -m novel_material.cli.main pipeline status nm_demo",
        "python -m novel_material.cli.main pipeline continue nm_demo",
    )
    assert all("{material_id}" not in action for action in actions)


def test_continue_persists_prior_successful_stages_without_counting_them(tmp_path):
    store = PipelineStateStore(tmp_path)
    orchestrator = PipelineOrchestrator(
        [spec("insights", RunStatus.SUCCESS)],
        state_store=store,
        prior_stages=(stage("analyze", RunStatus.SUCCESS),),
    )

    result = orchestrator.run(request())
    persisted = store.read_latest()

    assert [item.name for item in result.stages] == ["insights"]
    assert [item.name for item in persisted.stages] == ["analyze", "insights"]
