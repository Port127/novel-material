"""结构化运行日志核心行为测试。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from novel_material.run_logging.aggregation import DiagnosticAggregator
from novel_material.run_logging.reader import RunLogReadError, read_run_events
from novel_material.run_logging.retention import RetentionPolicy
from novel_material.run_logging.serializer import serialize_event
from novel_material.run_logging.sink import JsonlSink
from novel_material.run_logging.testing import MemoryLogSink
from novel_material.runtime.testing import event


def test_event_serializes_as_single_json_line():
    line = serialize_event(event("RunStarted"))
    payload = json.loads(line)

    assert "\n" not in line
    assert payload["schema_version"] == 1
    assert payload["occurred_at"].endswith("Z")
    assert payload["event_name"] == "RunStarted"


def test_sensitive_keys_and_values_are_redacted():
    source = event(
        "DiagnosticRaised",
        attributes={
            "authorization": "Bearer secret-token",
            "api_key": "sk-secret-value",
            "error_message": (
                "bad\nforged=INFO Bearer abc.def.ghi "
                "postgresql://writer:secret@db.example/novels"
            ),
            "prompt": "整段小说正文",
        },
    )

    payload = json.loads(serialize_event(source))
    attributes = payload["attributes"]

    assert attributes["authorization"] == "[REDACTED]"
    assert attributes["api_key"] == "[REDACTED]"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "整段小说正文" not in serialized
    assert "abc.def.ghi" not in serialized
    assert "writer:secret" not in serialized
    assert "\n" not in attributes["error_message"]


def test_jsonl_sink_rotates_without_touching_legacy_logs(tmp_path: Path):
    legacy = tmp_path / "pipeline_2026-06-21.log"
    legacy.write_text("legacy", encoding="utf-8")
    sink = JsonlSink(tmp_path, command="pipeline", run_id="run-1", max_bytes=220)

    for index in range(20):
        sink.emit(event("ProgressUpdated", attributes={"index": index}))
    sink.close()

    assert len(list(tmp_path.rglob("pipeline_run-1*.jsonl"))) > 1
    assert legacy.read_text(encoding="utf-8") == "legacy"


def test_memory_sink_never_creates_files(tmp_path: Path):
    sink = MemoryLogSink()
    sink.emit(event("RunStarted"))

    assert len(sink.events) == 1
    assert list(tmp_path.iterdir()) == []


def test_diagnostic_aggregator_limits_details_and_emits_summary():
    sink = MemoryLogSink()
    aggregator = DiagnosticAggregator(sink, detail_limit=2, sample_limit=3)

    for index in range(5):
        aggregator.emit(
            event(
                "DiagnosticRaised",
                stage_id="stage-1",
                attributes={
                    "diagnostic_code": "schema_invalid",
                    "message": f"第 {index} 项无效",
                },
            )
        )
    aggregator.flush()

    assert len(sink.events) == 3
    summary = sink.events[-1]
    assert summary.event_name == "DiagnosticSummaryRecorded"
    assert summary.attributes["diagnostic_code"] == "schema_invalid"
    assert summary.attributes["total_count"] == 5
    assert len(summary.attributes["samples"]) == 3


def test_retention_only_removes_expired_jsonl(tmp_path: Path):
    expired = tmp_path / "2026-05-01" / "pipeline_old.jsonl"
    current = tmp_path / "2026-06-22" / "pipeline_current.jsonl"
    active = tmp_path / "2026-05-01" / "pipeline_active.jsonl"
    legacy = tmp_path / "2025" / "pipeline.log"
    for path in (expired, current, active, legacy):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("data", encoding="utf-8")

    removed = RetentionPolicy(
        retention_days=30,
        max_files=200,
        today=date(2026, 6, 22),
    ).apply(tmp_path, active_paths={active})

    assert removed == (expired,)
    assert not expired.exists()
    assert current.exists()
    assert active.exists()
    assert legacy.exists()


def test_reader_merges_rotated_files_and_filters_run_id(tmp_path: Path):
    started_at = datetime(2026, 6, 23, 1, tzinfo=timezone.utc)
    started = event("RunStarted", run_id="run-1", occurred_at=started_at)
    completed = event(
        "RunCompleted",
        run_id="run-1",
        occurred_at=started_at + timedelta(seconds=1),
        status="success",
    )
    first = tmp_path / "2026-06-23/pipeline_run-1.jsonl"
    second = tmp_path / "2026-06-23/pipeline_run-1.1.jsonl"
    other = tmp_path / "2026-06-23/pipeline_run-2.jsonl"
    for path, events in (
        (first, [started]),
        (second, [completed, completed]),
        (other, [event("RunStarted", run_id="run-2")]),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(serialize_event(item) + "\n" for item in events),
            encoding="utf-8",
        )
    (tmp_path / "2026-06-23/pipeline_run-1.log").write_text(
        "legacy-bad-data", encoding="utf-8"
    )
    (tmp_path / "pipeline_run-1.jsonl").write_text(
        "root-bad-data", encoding="utf-8"
    )

    loaded = read_run_events(tmp_path, "run-1")

    assert [item.event_name for item in loaded] == [
        "RunStarted",
        "RunCompleted",
    ]


def test_reader_uses_sanitized_run_id_in_filename(tmp_path: Path):
    sink = JsonlSink(
        tmp_path,
        command="pipeline",
        run_id="run/unsafe",
        max_bytes=10000,
    )
    source = event("RunStarted", run_id="run/unsafe")
    sink.emit(source)

    loaded = read_run_events(tmp_path, "run/unsafe")

    assert loaded == (source,)


def test_reader_reports_corrupt_line_location(tmp_path: Path):
    path = tmp_path / "2026-06-23/pipeline_run-1.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        serialize_event(event("RunStarted", run_id="run-1")) + "\n{bad\n",
        encoding="utf-8",
    )

    with pytest.raises(RunLogReadError) as raised:
        read_run_events(tmp_path, "run-1")

    assert raised.value.path == path
    assert raised.value.line_number == 2
