from datetime import timedelta

from novel_material.reporting.models import PipelineRunReport
from novel_material.reporting.sink import ReportSink
from novel_material.reporting.writer import ReportWriter
from novel_material.runtime.contracts import RunEvent, RunStatus
from novel_material.runtime.dispatcher import SinkCriticality


def test_report_sink_writes_only_on_run_completed(
    tmp_path, sample_events: list[RunEvent]
) -> None:
    novel_dir = tmp_path / "nm_demo"
    sink = ReportSink(novel_dir)

    assert sink.name == "report"
    assert sink.criticality is SinkCriticality.REQUIRED
    assert sink.latest_report is None
    assert sink.latest_paths is None

    for item in sample_events[:-1]:
        sink.emit(item)
    assert not (novel_dir / "reports").exists()

    sink.emit(sample_events[-1])

    assert (novel_dir / "reports/latest.yaml").exists()
    assert sink.latest_report is not None
    assert sink.latest_report.run_id == "run-test"
    assert sink.latest_paths is not None


def test_report_sink_deduplicates_cached_events(
    tmp_path, sample_events: list[RunEvent]
) -> None:
    sink = ReportSink(tmp_path / "nm_demo")
    completed_operation = next(
        item for item in sample_events if item.event_name == "OperationCompleted"
    )

    for item in (*sample_events[:-1], completed_operation, sample_events[-1]):
        sink.emit(item)

    assert sink.latest_report is not None
    assert sink.latest_report.runtime.operation_completed == 1
    assert sink.latest_report.runtime.total_tokens == 150


def test_report_sink_uses_existing_history_for_baseline(
    tmp_path,
    sample_events: list[RunEvent],
    sample_report: PipelineRunReport,
) -> None:
    novel_dir = tmp_path / "nm_demo"
    prior = sample_report.model_copy(
        update={
            "run_id": "run-prior",
            "status": RunStatus.SUCCESS,
            "started_at": sample_report.started_at - timedelta(hours=1),
            "completed_at": sample_report.completed_at - timedelta(hours=1),
            "duration_ms": 10000,
        }
    )
    ReportWriter(novel_dir).write(prior)
    sink = ReportSink(novel_dir)

    for item in sample_events:
        sink.emit(item)

    assert sink.latest_report is not None
    assert sink.latest_report.baseline.kind == "same_material_command"
    assert sink.latest_report.baseline.baseline_duration_ms == 10000
