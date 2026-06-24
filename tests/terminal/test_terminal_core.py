"""终端模式、Reporter 与批次 ETA 测试。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from novel_material.audit.models import ArtifactIssue, AuditSeverity
from novel_material.reporting.models import (
    ArtifactQualityReport,
    PipelineRunReport,
    SeverityCounts,
)
from novel_material.runtime.contracts import Diagnostic, RunResult, RunStatus
from novel_material.runtime.testing import FakeClock
from novel_material.terminal.eta import BatchEtaEstimator
from novel_material.terminal.modes import TerminalMode, resolve_mode
from novel_material.terminal.reporter import TerminalReporter
from novel_material.terminal.testing import RecordingTerminal
from novel_material.terminal.progress import create_progress, finish_task


def sample_pipeline_report(
    status: RunStatus = RunStatus.DEGRADED,
) -> PipelineRunReport:
    started_at = datetime(2026, 6, 23, 1, tzinfo=timezone.utc)
    issues = (
        ArtifactIssue(
            code="character_profile_fallback",
            severity=AuditSeverity.ERROR,
            artifact="characters/profiles/主角.yaml",
            message="主要人物为空壳",
            next_actions=("nm pipeline characters nm_demo",),
        ),
    )
    return PipelineRunReport(
        run_id="run-test",
        material_id="nm_demo",
        command="pipeline full",
        status=status,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=20),
        duration_ms=20000,
        artifact_quality=ArtifactQualityReport(
            summary=SeverityCounts(error=1),
            issues=issues,
        ),
        next_actions=("nm pipeline characters nm_demo",),
    )


def test_eta_uses_batch_duration_not_burst_updates():
    clock = FakeClock()
    estimator = BatchEtaEstimator(clock=clock, min_samples=2, window=5)
    estimator.start(total=1780, completed=400)

    clock.advance(180)
    estimator.complete_batch(items=10)
    clock.advance(180)
    estimator.complete_batch(items=10)

    estimate = estimator.snapshot(completed=420)
    assert estimate.elapsed_seconds == 360
    assert 6 * 60 * 60 < estimate.remaining_seconds < 8 * 60 * 60
    assert estimate.remaining_seconds != 2


def test_eta_is_estimating_before_two_batches():
    estimator = BatchEtaEstimator(clock=FakeClock(), min_samples=2, window=5)
    estimator.start(total=100, completed=0)
    assert estimator.snapshot(completed=0).remaining_seconds is None


def test_resolve_mode_uses_plain_for_non_tty_or_no_progress():
    assert resolve_mode(json_output=False, quiet=False, no_progress=False, is_tty=False) is TerminalMode.PLAIN
    assert resolve_mode(json_output=False, quiet=False, no_progress=True, is_tty=True) is TerminalMode.PLAIN


def test_json_mode_keeps_stdout_parseable_and_diagnostics_on_stderr():
    terminal = RecordingTerminal()
    reporter = TerminalReporter(terminal, mode=TerminalMode.JSON)
    reporter.diagnostic(
        Diagnostic(
            code="database_unreachable",
            message="数据库不可达",
            severity="error",
        )
    )
    reporter.complete(
        RunResult.from_stages(run_id="run-1", command="pipeline status", stages=[])
    )

    assert json.loads(terminal.stdout_text)["status"] == "success"
    assert "database_unreachable" in terminal.stderr_text


def test_plain_progress_has_no_ansi_or_carriage_return():
    terminal = RecordingTerminal()
    reporter = TerminalReporter(terminal, mode=TerminalMode.PLAIN)
    reporter.progress(description="章级分析", completed=42, total=178)

    assert "\x1b[" not in terminal.stderr_text
    assert "\r" not in terminal.stderr_text


def test_dynamic_text_is_not_interpreted_as_rich_markup():
    terminal = RecordingTerminal()
    reporter = TerminalReporter(terminal, mode=TerminalMode.TTY)
    reporter.result_row(title="[red]危险[/red]", summary="正文")

    assert "[red]危险[/red]" in terminal.stderr_text


def test_terminal_completion_shows_report_path_and_top_risk():
    terminal = RecordingTerminal()
    reporter = TerminalReporter(terminal, mode=TerminalMode.PLAIN)

    reporter.complete_report(
        sample_pipeline_report(),
        Path("/tmp/reports/latest.md"),
    )

    output = terminal.stdout_text + terminal.stderr_text
    assert "degraded" in output
    assert "character_profile_fallback" in output
    assert "/tmp/reports/latest.md" in output
    assert "nm pipeline characters nm_demo" in output


def test_terminal_report_json_mode_keeps_stdout_parseable():
    terminal = RecordingTerminal()
    reporter = TerminalReporter(terminal, mode=TerminalMode.JSON)

    reporter.complete_report(
        sample_pipeline_report(),
        Path("/tmp/reports/latest.md"),
    )

    assert json.loads(terminal.stdout_text)["run_id"] == "run-test"
    assert terminal.stderr_text == ""


def test_terminal_report_quiet_success_has_no_output():
    terminal = RecordingTerminal()
    reporter = TerminalReporter(terminal, mode=TerminalMode.QUIET)
    report = sample_pipeline_report(RunStatus.SUCCESS).model_copy(
        update={
            "artifact_quality": ArtifactQualityReport(),
            "next_actions": (),
        }
    )

    reporter.complete_report(report, Path("/tmp/reports/latest.md"))

    assert terminal.stdout_text == ""
    assert terminal.stderr_text == ""


def test_indeterminate_progress_has_explicit_terminal_status():
    terminal = RecordingTerminal()
    reporter = TerminalReporter(terminal, mode=TerminalMode.PLAIN)
    progress = create_progress(console=reporter.stderr)
    task_id = progress.add_task("素材分类", total=None)

    finish_task(progress, task_id, status="degraded")

    task = progress.tasks[0]
    assert task.finished is True
    assert task.description.startswith("△")
