"""PipelineOrchestrator 结果与故障语义测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from novel_material.audit.models import ArtifactAudit
from novel_material.pipeline import stages as stage_entries
from novel_material.pipeline.orchestrator import (
    PipelineOrchestrator,
    RunRequest,
    StageContractError,
    StageSpec,
    render_next_actions,
)
from novel_material.runtime.contracts import ProgressCounts, RunStatus, StageResult
from novel_material.runtime.context import run_context, stage_context
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


def test_blocker_audit_stops_before_sync():
    calls: list[str] = []
    sync = StageSpec(
        "sync",
        lambda _request: calls.append("sync")
        or stage("sync", RunStatus.SUCCESS),
        blocking=True,
    )

    result = PipelineOrchestrator(
        [
            spec("analyze", RunStatus.SUCCESS),
            spec("audit", RunStatus.FAILED, blocking=True),
            sync,
        ]
    ).run(request())

    assert [item.name for item in result.stages] == ["analyze", "audit"]
    assert result.status is RunStatus.FAILED
    assert calls == []


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
        "insights", "refine", "profile", "audit", "release_gate", "sync",
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
    assert plan.stage_names == (
        "insights",
        "refine",
        "profile",
        "audit",
        "release_gate",
        "sync",
    )


def test_continue_plan_starts_from_evaluation_when_navigation_enabled():
    stages = {
        name: stage(name, RunStatus.SUCCESS)
        for name in (
            "analyze",
            "outline",
            "worldbuilding",
            "characters",
            "tags",
            "insights",
            "refine",
            "profile",
            "audit",
            "release_gate",
            "sync",
        )
    }
    inspection = SimpleNamespace(exists=True, stages=stages)

    plan = PipelineOrchestrator.plan_continue(
        inspection,
        include_navigation=True,
    )

    assert plan.first_stage == "evaluation"
    assert plan.stage_names == (
        "evaluation",
        "analyze",
        "outline",
        "worldbuilding",
        "characters",
        "tags",
        "insights",
        "refine",
        "profile",
        "audit",
        "release_gate",
        "sync",
    )


def test_continue_plan_skips_missing_evaluation_when_navigation_disabled():
    stages = {
        name: stage(name, RunStatus.SUCCESS)
        for name in (
            "analyze",
            "outline",
            "worldbuilding",
            "characters",
            "tags",
            "insights",
            "refine",
            "profile",
            "audit",
            "release_gate",
            "sync",
        )
    }
    inspection = SimpleNamespace(exists=True, stages=stages)

    plan = PipelineOrchestrator.plan_continue(
        inspection,
        include_navigation=False,
    )

    assert plan.stage_names == ()


def test_continue_plan_starts_at_audit_for_old_sidecar_without_audit():
    stages = {
        name: stage(name, RunStatus.SUCCESS)
        for name in (
            "analyze",
            "outline",
            "worldbuilding",
            "characters",
            "tags",
            "insights",
            "refine",
            "sync",
        )
    }
    inspection = SimpleNamespace(exists=True, stages=stages)

    plan = PipelineOrchestrator.plan_continue(inspection)

    assert plan.stage_names == ("profile", "audit", "release_gate", "sync")


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


def test_stage_completed_event_contains_name_duration_counts_and_diagnostics():
    sink = MemoryEventSink()
    ticks = iter((10.0, 10.25))
    source = StageResult(
        stage_id="stage-analyze",
        name="analyze",
        status=RunStatus.DEGRADED,
        counts=ProgressCounts(
            expected=2,
            processed=2,
            succeeded=1,
            degraded=1,
            remaining=0,
        ),
    )
    orchestrator = PipelineOrchestrator(
        [StageSpec("analyze", lambda _request: source, blocking=False)],
        dispatcher=RuntimeDispatcher([sink]),
        clock=lambda: next(ticks),
    )

    result = orchestrator.run(request())

    completed = sink.events_named("StageCompleted")[0]
    assert completed.attributes["stage_name"] == "analyze"
    assert completed.attributes["counts"] == result.stages[0].counts.model_dump(
        mode="json"
    )
    assert completed.attributes["diagnostics"] == []
    assert completed.duration_ms == pytest.approx(250)
    assert result.stages[0].duration_ms == pytest.approx(250)


def test_unhandled_stage_exception_becomes_failed_result_and_run_completed_event():
    sink = MemoryEventSink()
    broken = StageSpec(
        "analyze",
        lambda _request: (_ for _ in ()).throw(ValueError("bad payload")),
        blocking=True,
    )

    result = PipelineOrchestrator(
        [broken],
        dispatcher=RuntimeDispatcher([sink]),
    ).run(request())

    assert result.status is RunStatus.FAILED
    assert result.diagnostics[0].code == "stage_unhandled_exception"
    assert result.diagnostics[0].message.endswith("ValueError")
    assert "bad payload" not in result.diagnostics[0].message
    assert sink.events_named("RunCompleted")


def test_run_boundary_events_include_started_at_prior_stages_and_final_result():
    sink = MemoryEventSink()
    started_at = datetime(2026, 6, 23, 1, tzinfo=timezone.utc)
    ingest = stage("ingest", RunStatus.SUCCESS)
    run_request = RunRequest(
        run_id="run-1",
        command="pipeline full",
        material_id="nm_demo",
        started_at=started_at,
        options={"report_prior_stages": (ingest,)},
    )

    result = PipelineOrchestrator(
        [spec("analyze", RunStatus.SUCCESS)],
        dispatcher=RuntimeDispatcher([sink]),
    ).run(run_request)

    started = sink.events_named("RunStarted")[0]
    completed = sink.events_named("RunCompleted")[0]
    assert started.occurred_at == started_at
    assert started.attributes["report_prior_stages"][0]["name"] == "ingest"
    assert "outputs" not in started.attributes["report_prior_stages"][0]
    assert completed.attributes["counts"] == result.counts.model_dump(mode="json")
    assert completed.attributes["diagnostics"] == []


def test_artifact_audit_stage_publishes_domain_event(monkeypatch):
    sink = MemoryEventSink()
    dispatcher = RuntimeDispatcher([sink])
    audit = ArtifactAudit(material_id="nm_demo", checks=("characters",))
    monkeypatch.setattr(stage_entries, "audit_material", lambda *_args, **_kwargs: audit)

    with run_context(
        "pipeline full",
        "nm_demo",
        run_id="run-1",
        dispatcher=dispatcher,
    ):
        with stage_context("audit"):
            result = stage_entries.run_artifact_audit_stage("nm_demo")

    completed = sink.events_named("ArtifactAuditCompleted")
    assert result.status is RunStatus.SUCCESS
    assert len(completed) == 1
    assert completed[0].attributes == {"audit": audit.model_dump(mode="json")}
