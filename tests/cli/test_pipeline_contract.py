"""Pipeline CLI 的结果和退出码契约。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner
import pytest

from novel_material.cli.main import app
from novel_material.audit.models import ArtifactIssue, AuditSeverity
from novel_material.reporting.models import (
    ArtifactQualityReport,
    PipelineRunReport,
    SeverityCounts,
)
from novel_material.run_logging.serializer import serialize_event
from novel_material.runtime.contracts import RunResult, RunStatus, StageResult
from novel_material.pipeline.orchestrator import StageSpec
from novel_material.pipeline.state import (
    ConcurrentRunError,
    PersistedRunState,
    PipelineStateCorruptError,
    PipelineStateStore,
)
from novel_material.runtime.testing import event


runner = CliRunner()


def failed_stage(name: str) -> StageResult:
    return StageResult(stage_id=f"stage-{name}", name=name, status=RunStatus.FAILED)


def report_with_risk() -> PipelineRunReport:
    started_at = datetime(2026, 6, 23, 1, tzinfo=timezone.utc)
    return PipelineRunReport(
        run_id="run-test",
        material_id="nm_demo",
        command="pipeline full",
        status=RunStatus.DEGRADED,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=20),
        duration_ms=20000,
        artifact_quality=ArtifactQualityReport(
            summary=SeverityCounts(error=1),
            issues=(
                ArtifactIssue(
                    code="character_profile_fallback",
                    severity=AuditSeverity.ERROR,
                    artifact="characters/profiles/主角.yaml",
                    message="主要人物为空壳",
                    next_actions=("nm pipeline characters nm_demo",),
                ),
            ),
        ),
        next_actions=("nm pipeline characters nm_demo",),
    )


def test_ingest_failure_exits_one(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_ingest_stage",
        lambda *_args, **_kwargs: failed_stage("ingest"),
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", "ingest", "missing.txt"])

    assert result.exit_code == 1
    assert "入库失败" in result.stderr
    assert "入库成功" not in result.stdout


def test_outline_failure_exits_one(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_outline_stage",
        lambda *_args, **_kwargs: failed_stage("outline"),
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", "outline", "nm_demo"])

    assert result.exit_code == 1
    assert "大纲生成失败" in result.stderr
    assert "大纲生成完成" not in result.stdout


def test_missing_material_status_is_not_complete(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.inspect_pipeline_state",
        lambda _material_id: SimpleNamespace(exists=False, stages={}),
    )

    result = runner.invoke(app, ["pipeline", "status", "nm_missing"])

    assert result.exit_code == 1
    assert "素材目录不存在" in result.stderr
    assert "流水线已完成" not in result.stdout + result.stderr


def test_status_reads_pipeline_inspection_instead_of_legacy_progress(monkeypatch):
    inspection = SimpleNamespace(
        exists=True,
        stages={"analyze": failed_stage("analyze")},
    )
    monkeypatch.setattr(
        "novel_material.cli.pipeline.inspect_pipeline_state",
        lambda _material_id: inspection,
        raising=False,
    )
    monkeypatch.setattr(
        "novel_material.cli.pipeline.get_pipeline_progress",
        lambda _material_id: (_ for _ in ()).throw(AssertionError("不应读取旧进度")),
    )

    result = runner.invoke(app, ["pipeline", "status", "nm_demo"])

    assert result.exit_code == 0
    assert "analyze" in result.stdout
    assert "下一步: nm pipeline continue nm_demo" in result.stdout


@pytest.mark.parametrize(
    ("command", "entrypoint", "message"),
    [
        ("worldbuilding", "run_worldbuilding_stage", "世界观提取失败"),
        ("characters", "run_characters_stage", "人物提取失败"),
        ("tags", "run_tags_stage", "标签生成失败"),
        ("refine", "run_refine_stage", "精调失败"),
    ],
)
def test_remaining_single_stage_failures_exit_one(
    monkeypatch,
    command,
    entrypoint,
    message,
):
    monkeypatch.setattr(
        f"novel_material.cli.pipeline.{entrypoint}",
        lambda *_args, **_kwargs: failed_stage(command),
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", command, "nm_demo"])

    assert result.exit_code == 1
    assert message in result.stderr
    assert "完成" not in result.stdout


def test_full_uses_run_result_exit_code(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_full_pipeline",
        lambda **_kwargs: RunResult.from_stages(
            run_id="run-1",
            command="pipeline full",
            stages=[failed_stage("analyze")],
        ),
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", "full", "novel.txt"])

    assert result.exit_code == 1
    assert "流水线失败" in result.stderr


def test_continue_uses_run_result_degraded_exit_code(monkeypatch):
    degraded = StageResult(
        stage_id="stage-insights",
        name="insights",
        status=RunStatus.DEGRADED,
    )
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_continue_pipeline",
        lambda **_kwargs: RunResult.from_stages(
            run_id="run-1",
            command="pipeline continue",
            stages=[degraded],
        ),
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", "continue", "nm_demo"])

    assert result.exit_code == 3
    assert "降级完成" in result.stderr


def test_full_uses_report_sink_summary_but_keeps_run_result_exit_code(
    monkeypatch,
):
    report = report_with_risk()
    sink = SimpleNamespace(
        latest_report=report,
        latest_paths=SimpleNamespace(
            latest_markdown=Path("/tmp/reports/latest.md")
        ),
    )

    def fake_full(**kwargs):
        kwargs["runtime_observer"](
            SimpleNamespace(report_sink=sink)
        )
        return RunResult.from_stages(
            run_id="run-test",
            command="pipeline full",
            stages=[
                StageResult(
                    stage_id="stage-audit",
                    name="audit",
                    status=RunStatus.DEGRADED,
                )
            ],
        )

    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_full_pipeline",
        fake_full,
    )

    result = runner.invoke(app, ["pipeline", "full", "novel.txt"])

    assert result.exit_code == 3
    assert "character_profile_fallback" in result.stderr
    assert "/tmp/reports/latest.md" in result.stderr


def test_pipeline_report_rebuilds_latest_run_without_changing_facts(
    tmp_path, monkeypatch
):
    material_id = "nm_demo"
    run_id = "run-test"
    novel_dir = tmp_path / "novels" / material_id
    novel_dir.mkdir(parents=True)
    fact = novel_dir / "meta.yaml"
    fact.write_text("status: finalized\n", encoding="utf-8")
    before = fact.read_bytes()
    started_at = datetime(2026, 6, 23, 1, tzinfo=timezone.utc)
    PipelineStateStore(novel_dir).write(
        PersistedRunState(
            run_id=run_id,
            command="pipeline full",
            status=RunStatus.SUCCESS,
            generation=1,
            created_at=started_at,
            updated_at=started_at + timedelta(seconds=20),
        )
    )
    log_dir = tmp_path / "logs"
    log_path = log_dir / "2026-06-23/pipeline_run-test.jsonl"
    log_path.parent.mkdir(parents=True)
    events = (
        event(
            "RunStarted",
            run_id=run_id,
            command="pipeline full",
            material_id=material_id,
            occurred_at=started_at,
        ),
        event(
            "RunCompleted",
            run_id=run_id,
            command="pipeline full",
            material_id=material_id,
            occurred_at=started_at + timedelta(seconds=20),
            status=RunStatus.SUCCESS,
            attributes={"counts": {}, "diagnostics": []},
        ),
    )
    log_path.write_text(
        "".join(serialize_event(item) + "\n" for item in events),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "novel_material.cli.pipeline.NOVELS_DIR",
        tmp_path / "novels",
    )
    monkeypatch.setattr(
        "novel_material.cli.pipeline.ensure_log_dir",
        lambda: log_dir,
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", "report", material_id])

    assert result.exit_code == 0
    assert (novel_dir / "reports/latest.yaml").exists()
    assert str(novel_dir / "reports/latest.md") in result.stdout
    assert fact.read_bytes() == before


def test_pipeline_report_missing_events_has_stable_error(tmp_path, monkeypatch):
    novels_dir = tmp_path / "novels"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(
        "novel_material.cli.pipeline.NOVELS_DIR",
        novels_dir,
    )
    monkeypatch.setattr(
        "novel_material.cli.pipeline.ensure_log_dir",
        lambda: log_dir,
        raising=False,
    )

    result = runner.invoke(
        app,
        ["pipeline", "report", "nm_demo", "--run-id", "run-missing"],
    )

    assert result.exit_code == 1
    assert "run_events_missing" in result.stderr
    assert not (novels_dir / "nm_demo/reports").exists()


def test_continue_rejects_second_writer_for_same_material(tmp_path, monkeypatch):
    material_id = "nm_demo"
    novel_dir = tmp_path / material_id
    novel_dir.mkdir()
    store = PipelineStateStore(novel_dir)
    inspection = SimpleNamespace(exists=True, stages={})
    monkeypatch.setattr("novel_material.cli.pipeline_common.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.cli.pipeline_common.inspect_pipeline_state",
        lambda *_args, **_kwargs: inspection,
    )
    monkeypatch.setattr(
        "novel_material.cli.pipeline_common._stage_specs",
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

    with store.acquire_lease("run-existing"):
        with pytest.raises(ConcurrentRunError, match="pipeline_run_already_active"):
            from novel_material.cli.pipeline_common import run_continue_pipeline

            run_continue_pipeline(material_id=material_id)


def test_full_keyboard_interrupt_exits_130_without_traceback(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_full_pipeline",
        lambda **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    result = runner.invoke(app, ["pipeline", "full", "novel.txt"])

    assert result.exit_code == 130
    assert "运行已中断" in result.stderr
    assert "Traceback" not in result.stderr


def test_continue_interrupted_result_exits_130(monkeypatch):
    interrupted = StageResult(
        stage_id="stage-analyze",
        name="analyze",
        status=RunStatus.INTERRUPTED,
    )
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_continue_pipeline",
        lambda **_kwargs: RunResult.from_stages(
            run_id="run-1",
            command="pipeline continue",
            stages=[interrupted],
        ),
    )

    result = runner.invoke(app, ["pipeline", "continue", "nm_demo"])

    assert result.exit_code == 130
    assert "运行已中断" in result.stderr
    assert "流水线失败" not in result.stderr


def test_continue_active_lease_has_stable_cli_error(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_continue_pipeline",
        lambda **_kwargs: (_ for _ in ()).throw(
            ConcurrentRunError("pipeline_run_already_active")
        ),
    )

    result = runner.invoke(app, ["pipeline", "continue", "nm_demo"])

    assert result.exit_code == 1
    assert "pipeline_run_already_active" in result.stderr
    assert "Traceback" not in result.stderr


def test_status_corrupt_sidecar_has_stable_cli_error(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.inspect_pipeline_state",
        lambda _material_id: (_ for _ in ()).throw(
            PipelineStateCorruptError("latest 索引无效")
        ),
    )

    result = runner.invoke(app, ["pipeline", "status", "nm_demo"])

    assert result.exit_code == 1
    assert "state_corrupt" in result.stderr
    assert "Traceback" not in result.stderr
