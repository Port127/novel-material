from datetime import timedelta

import pytest
import yaml

from novel_material.infra.path_service import PathService
from novel_material.reporting.models import PipelineRunReport
from novel_material.reporting.writer import (
    ReportConflictError,
    ReportHistoryError,
    ReportWriter,
)


def test_writer_creates_immutable_run_and_atomic_latest_files(
    tmp_path, sample_report: PipelineRunReport
) -> None:
    writer = ReportWriter(tmp_path / "nm_demo")

    paths = writer.write(sample_report)

    assert paths.run_yaml == tmp_path / "nm_demo/reports/runs/run-test.yaml"
    assert paths.latest_yaml.read_text(
        encoding="utf-8"
    ) == paths.run_yaml.read_text(encoding="utf-8")
    assert paths.latest_markdown.exists()
    assert not list((tmp_path / "nm_demo/reports").rglob("*.tmp"))
    assert yaml.safe_load(paths.run_yaml.read_text(encoding="utf-8"))[
        "run_id"
    ] == "run-test"


def test_writer_is_idempotent_for_identical_run_report(
    tmp_path, sample_report: PipelineRunReport
) -> None:
    writer = ReportWriter(tmp_path / "nm_demo")
    first = writer.write(sample_report)

    second = writer.write(sample_report)

    assert second == first


def test_writer_rejects_conflicting_immutable_run_report(
    tmp_path, sample_report: PipelineRunReport
) -> None:
    writer = ReportWriter(tmp_path / "nm_demo")
    writer.write(sample_report)
    changed = sample_report.model_copy(update={"command": "pipeline analyze"})

    with pytest.raises(ReportConflictError, match="run-test"):
        writer.write(changed)


def test_writer_loads_history_sorted_by_completion_time(
    tmp_path, sample_report: PipelineRunReport
) -> None:
    writer = ReportWriter(tmp_path / "nm_demo")
    older = sample_report.model_copy(
        update={
            "run_id": "run-old",
            "started_at": sample_report.started_at - timedelta(hours=1),
            "completed_at": sample_report.completed_at - timedelta(hours=1),
        }
    )
    writer.write(sample_report)
    writer.write(older)

    history = writer.load_history()

    assert [item.run_id for item in history] == ["run-old", "run-test"]


def test_writer_rejects_corrupt_history(
    tmp_path, sample_report: PipelineRunReport
) -> None:
    writer = ReportWriter(tmp_path / "nm_demo")
    writer.write(sample_report)
    broken = tmp_path / "nm_demo/reports/runs/broken.yaml"
    broken.write_text("status: [", encoding="utf-8")

    with pytest.raises(ReportHistoryError, match="broken.yaml"):
        writer.load_history()


def test_writer_wraps_invalid_utf8_history(
    tmp_path, sample_report: PipelineRunReport
) -> None:
    writer = ReportWriter(tmp_path / "nm_demo")
    writer.write(sample_report)
    broken = tmp_path / "nm_demo/reports/runs/invalid-utf8.yaml"
    broken.write_bytes(b"\xff")

    with pytest.raises(ReportHistoryError, match="invalid-utf8.yaml"):
        writer.load_history()


def test_path_service_exposes_report_layout(tmp_path) -> None:
    paths = PathService(tmp_path)

    assert paths.reports_dir("nm_demo") == tmp_path / "nm_demo/reports"
    assert paths.report_run_path("nm_demo", "run-1") == (
        tmp_path / "nm_demo/reports/runs/run-1.yaml"
    )
    assert paths.report_latest_yaml_path("nm_demo") == (
        tmp_path / "nm_demo/reports/latest.yaml"
    )
    assert paths.report_latest_markdown_path("nm_demo") == (
        tmp_path / "nm_demo/reports/latest.md"
    )
