"""完整流水线统一阶段计划测试。"""

from types import SimpleNamespace

from novel_material.cli import pipeline_common
from novel_material.pipeline.orchestrator import RunRequest, StageSpec
from novel_material.runtime.contracts import (
    Diagnostic,
    RunResult,
    RunStatus,
    StageResult,
)
from novel_material.runtime.dispatcher import RuntimeDispatcher, SinkCriticality
from novel_material.runtime.testing import MemoryEventSink, event


def _record_insights_call(monkeypatch, *, mode: str) -> dict:
    recorded = {}

    def fake_run_insights_stage(material_id, **kwargs):
        recorded.update(material_id=material_id, **kwargs)
        return StageResult(
            stage_id="stage-insights",
            name="insights",
            status=RunStatus.SUCCESS,
        )

    monkeypatch.setattr(
        pipeline_common,
        "run_insights_stage",
        fake_run_insights_stage,
    )
    spec = next(
        stage
        for stage in pipeline_common._stage_specs("nm_demo", {"mode": mode})
        if stage.name == "insights"
    )
    request = RunRequest(
        run_id="run-test",
        command="pipeline full",
        material_id="nm_demo",
    )
    assert spec.enabled(request) is True
    spec.execute(request)
    return recorded


def test_standard_pipeline_limits_automatic_insights_to_first_100(monkeypatch):
    monkeypatch.setattr(
        pipeline_common,
        "get_runtime_mode",
        lambda _name: type(
            "Mode",
            (),
            {"include_core_insights": True, "core_insight_chapter_limit": 100},
        )(),
    )

    recorded = _record_insights_call(monkeypatch, mode="standard")

    assert recorded == {
        "material_id": "nm_demo",
        "start_ch": 1,
        "end_ch": 100,
        "provider": None,
    }


def test_deep_pipeline_keeps_automatic_core_insights_unbounded(monkeypatch):
    monkeypatch.setattr(
        pipeline_common,
        "get_runtime_mode",
        lambda _name: type(
            "Mode",
            (),
            {"include_core_insights": True, "core_insight_chapter_limit": None},
        )(),
    )

    recorded = _record_insights_call(monkeypatch, mode="deep")

    assert recorded == {
        "material_id": "nm_demo",
        "start_ch": None,
        "end_ch": None,
        "provider": None,
    }


def test_explicit_pipeline_range_overrides_standard_default(monkeypatch):
    monkeypatch.setattr(
        pipeline_common,
        "get_runtime_mode",
        lambda _name: type(
            "Mode",
            (),
            {"include_core_insights": True, "core_insight_chapter_limit": 100},
        )(),
    )
    recorded = {}

    def fake_run_insights_stage(material_id, **kwargs):
        recorded.update(material_id=material_id, **kwargs)
        return StageResult(
            stage_id="stage-insights",
            name="insights",
            status=RunStatus.SUCCESS,
        )

    monkeypatch.setattr(
        pipeline_common,
        "run_insights_stage",
        fake_run_insights_stage,
    )
    options = {"mode": "standard", "start": 300, "end": 350}
    spec = next(
        stage
        for stage in pipeline_common._stage_specs("nm_demo", options)
        if stage.name == "insights"
    )
    spec.execute(
        RunRequest(
            run_id="run-test",
            command="pipeline continue",
            material_id="nm_demo",
        )
    )

    assert recorded["start_ch"] == 300
    assert recorded["end_ch"] == 350


def test_stage_plan_places_blocking_audit_before_sync():
    specs = pipeline_common._stage_specs(
        "nm_demo",
        {"mode": "fast"},
        elapsed_provider=lambda: 0.0,
    )

    assert [item.name for item in specs][-3:] == ["refine", "audit", "sync"]
    assert next(item for item in specs if item.name == "audit").blocking is True


def test_pipeline_runtime_registers_jsonl_and_report_sinks(
    tmp_path, monkeypatch
):
    novels_dir = tmp_path / "novels"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(pipeline_common, "NOVELS_DIR", novels_dir)
    monkeypatch.setattr(pipeline_common, "ensure_log_dir", lambda: log_dir)
    monkeypatch.setattr(
        pipeline_common,
        "get_settings",
        lambda: {"RUN_LOG_MAX_BYTES": 10000},
    )

    runtime = pipeline_common._create_pipeline_runtime(
        "nm_demo",
        "pipeline full",
        "run-test",
    )
    delivered = runtime.dispatcher.emit(
        event(
            "RunStarted",
            run_id="run-test",
            command="pipeline full",
            material_id="nm_demo",
        )
    )

    assert delivered.delivered == 2
    assert runtime.report_sink.writer.novel_dir == novels_dir / "nm_demo"
    assert len(list(log_dir.rglob("*.jsonl"))) == 1
    assert not (novels_dir / "nm_demo/reports").exists()


def test_fast_audit_uses_rules_without_reviewer(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        pipeline_common,
        "run_artifact_audit_stage",
        lambda material_id, **kwargs: captured.update(
            material_id=material_id, kwargs=kwargs
        )
        or StageResult(
            stage_id="stage-audit",
            name="audit",
            status=RunStatus.SUCCESS,
        ),
    )
    audit = next(
        item
        for item in pipeline_common._stage_specs(
            "nm_demo",
            {"mode": "fast"},
            elapsed_provider=lambda: 90.0,
        )
        if item.name == "audit"
    )

    audit.execute(
        RunRequest(
            run_id="run-test",
            command="pipeline full",
            material_id="nm_demo",
        )
    )

    assert captured == {"material_id": "nm_demo", "kwargs": {}}


def test_standard_audit_budget_uses_elapsed_fraction(monkeypatch):
    captured = {}
    reviewer = object()
    monkeypatch.setattr(pipeline_common, "LLMArtifactReviewer", lambda: reviewer)
    monkeypatch.setattr(
        pipeline_common,
        "get_settings",
        lambda: {
            "ARTIFACT_REVIEW_TIME_FRACTION_STANDARD": 0.10,
            "ARTIFACT_REVIEW_MAX_CALLS_STANDARD": 3,
            "ARTIFACT_REVIEW_MAX_CALLS_DEEP": 10,
        },
    )
    monkeypatch.setattr(
        pipeline_common,
        "run_artifact_audit_stage",
        lambda material_id, **kwargs: captured.update(
            material_id=material_id, **kwargs
        )
        or StageResult(
            stage_id="stage-audit",
            name="audit",
            status=RunStatus.SUCCESS,
        ),
    )
    audit = next(
        item
        for item in pipeline_common._stage_specs(
            "nm_demo",
            {"mode": "standard"},
            elapsed_provider=lambda: 50.0,
        )
        if item.name == "audit"
    )

    audit.execute(
        RunRequest(
            run_id="run-test",
            command="pipeline full",
            material_id="nm_demo",
        )
    )

    assert captured["reviewer"] is reviewer
    assert captured["budget"].max_seconds == 5.0
    assert captured["budget"].max_calls == 3


def test_combine_run_result_preserves_top_level_observability_diagnostic():
    ingest = StageResult(
        stage_id="stage-ingest",
        name="ingest",
        status=RunStatus.SUCCESS,
    )
    analyze = StageResult(
        stage_id="stage-analyze",
        name="analyze",
        status=RunStatus.SUCCESS,
    )
    remainder = RunResult.from_stages(
        "run-test",
        "pipeline full",
        [analyze],
    ).model_copy(
        update={
            "status": RunStatus.DEGRADED,
            "exit_code": 3,
            "diagnostics": (
                Diagnostic(
                    code="event_sink_failed",
                    message="required sink 写入失败: report",
                    severity="warning",
                ),
            ),
        }
    )

    combined = pipeline_common.combine_run_result(
        (ingest,),
        remainder,
        expected_stages=2,
    )

    assert combined.status is RunStatus.DEGRADED
    assert combined.exit_code == 3
    assert combined.diagnostics[-1].code == "event_sink_failed"


def test_full_preserves_report_sink_failure_and_ingest_timing(
    tmp_path, monkeypatch
):
    memory = MemoryEventSink()

    class BrokenReportSink:
        name = "report"
        criticality = SinkCriticality.REQUIRED

        def emit(self, event):
            if event.event_name == "RunCompleted":
                raise OSError("disk full")

    broken = BrokenReportSink()
    runtime = SimpleNamespace(
        dispatcher=RuntimeDispatcher([memory, broken]),
        report_sink=broken,
    )
    ingest = StageResult(
        stage_id="stage-ingest",
        name="ingest",
        status=RunStatus.SUCCESS,
        outputs={"material_id": "nm_demo"},
    )
    ticks = iter((10.0, 10.25))
    monkeypatch.setattr(pipeline_common, "NOVELS_DIR", tmp_path)
    monkeypatch.setattr(pipeline_common, "run_ingest_stage", lambda _path: ingest)
    monkeypatch.setattr(pipeline_common.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        pipeline_common,
        "_create_pipeline_runtime",
        lambda *_args: runtime,
    )
    monkeypatch.setattr(
        pipeline_common,
        "_stage_specs",
        lambda *_args, **_kwargs: (
            StageSpec(
                "analyze",
                lambda _request: StageResult(
                    stage_id="stage-analyze",
                    name="analyze",
                    status=RunStatus.SUCCESS,
                ),
                blocking=True,
            ),
        ),
    )

    observed_runtimes = []
    result = pipeline_common.run_full_pipeline(
        file_path="novel.txt",
        runtime_observer=observed_runtimes.append,
    )

    assert result.status is RunStatus.DEGRADED
    assert observed_runtimes == [runtime]
    assert result.diagnostics[-1].code == "event_sink_failed"
    assert result.stages[0].duration_ms == 250
    started = memory.events_named("RunStarted")[0]
    assert started.occurred_at.tzinfo is not None
    assert started.attributes["report_prior_stages"][0]["name"] == "ingest"


def test_continue_runtime_does_not_report_historical_stages(
    tmp_path, monkeypatch
):
    memory = MemoryEventSink()
    runtime = SimpleNamespace(
        dispatcher=RuntimeDispatcher([memory]),
        report_sink=None,
    )
    prior = StageResult(
        stage_id="stage-analyze",
        name="analyze",
        status=RunStatus.SUCCESS,
    )
    inspection = SimpleNamespace(exists=True, stages={"analyze": prior})
    monkeypatch.setattr(pipeline_common, "NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        pipeline_common,
        "inspect_pipeline_state",
        lambda *_args, **_kwargs: inspection,
    )
    monkeypatch.setattr(
        pipeline_common,
        "_create_pipeline_runtime",
        lambda *_args: runtime,
    )
    monkeypatch.setattr(
        pipeline_common,
        "_stage_specs",
        lambda *_args, **_kwargs: (
            StageSpec(
                "audit",
                lambda _request: StageResult(
                    stage_id="stage-audit",
                    name="audit",
                    status=RunStatus.SUCCESS,
                ),
                blocking=True,
            ),
        ),
    )
    monkeypatch.setattr(
        pipeline_common.PipelineOrchestrator,
        "plan_continue",
        lambda _inspection: SimpleNamespace(stage_names=("audit",)),
    )

    observed_runtimes = []
    pipeline_common.run_continue_pipeline(
        material_id="nm_demo",
        runtime_observer=observed_runtimes.append,
    )

    assert observed_runtimes == [runtime]
    started = memory.events_named("RunStarted")[0]
    assert started.attributes["report_prior_stages"] == []
