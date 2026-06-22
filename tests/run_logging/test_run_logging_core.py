"""结构化运行日志核心行为测试。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from novel_material.run_logging.aggregation import DiagnosticAggregator
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
