"""Pipeline 运行状态 sidecar 测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from novel_material.pipeline.state import (
    ConcurrentRunError,
    PersistedRunState,
    PipelineStateCorruptError,
    PipelineStateStore,
)
from novel_material.runtime.contracts import RunStatus
from novel_material.pipeline.progress import (
    inspect_pipeline_state,
    next_pending_stage,
    probe_database_status,
)


def run_state(run_id: str, status: RunStatus, generation: int = 1) -> PersistedRunState:
    now = datetime.now(timezone.utc)
    return PersistedRunState(
        run_id=run_id,
        command="pipeline full",
        status=status,
        generation=generation,
        created_at=now,
        updated_at=now,
    )


def test_state_store_replaces_file_and_latest_index_atomically(tmp_path: Path):
    store = PipelineStateStore(tmp_path)
    store.write(run_state("run-1", RunStatus.RUNNING, generation=1))
    store.write(run_state("run-1", RunStatus.DEGRADED, generation=2))

    assert store.read("run-1").status is RunStatus.DEGRADED
    assert store.read_latest().run_id == "run-1"
    assert store.read_latest().generation == 2
    assert not list((tmp_path / "runs").glob("*.tmp"))


def test_latest_state_uses_index_not_filename(tmp_path: Path):
    store = PipelineStateStore(tmp_path)
    store.write(run_state("run-z", RunStatus.SUCCESS))
    store.write(run_state("run-a", RunStatus.FAILED))

    assert store.read_latest().run_id == "run-a"


def test_second_writer_for_same_material_is_rejected(tmp_path: Path):
    store = PipelineStateStore(tmp_path, process_probe=lambda _pid: True)

    with store.acquire_lease("run-1"):
        with pytest.raises(ConcurrentRunError):
            with store.acquire_lease("run-2"):
                pass


def test_corrupt_latest_index_does_not_fall_back(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "latest.json").write_text("{bad", encoding="utf-8")

    with pytest.raises(PipelineStateCorruptError):
        PipelineStateStore(tmp_path).read_latest()


def test_database_probe_error_is_unknown(monkeypatch):
    monkeypatch.setattr(
        "novel_material.pipeline.progress.psycopg2.connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )

    result = probe_database_status("nm_demo")

    assert result.status == "unknown"
    assert result.diagnostic.code == "database_unreachable"


def test_invalid_legacy_insights_are_pending_without_writing_sidecar(
    tmp_path: Path,
    monkeypatch,
):
    material_id = "nm_legacy"
    novel_dir = tmp_path / material_id
    novel_dir.mkdir()
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 1\n- chapter: 2\n",
        encoding="utf-8",
    )
    (novel_dir / "chapters.yaml").write_text(
        "- chapter: 1\n- chapter: 2\n",
        encoding="utf-8",
    )
    for directory in ("outline", "worldbuilding", "characters"):
        target = novel_dir / directory
        target.mkdir()
        (target / "_index.yaml").write_text("[]\n", encoding="utf-8")
    (novel_dir / "tags.yaml").write_text("{}\n", encoding="utf-8")
    insights = novel_dir / "chapter_insights"
    insights.mkdir()
    (insights / "0001.yaml").write_text("chapter: 1\n", encoding="utf-8")
    (insights / "0002.yaml").write_text("chapter: 2\n", encoding="utf-8")
    monkeypatch.setattr(
        "novel_material.pipeline.progress.probe_database_status",
        lambda _material_id: type("Probe", (), {"status": "not_synced", "diagnostic": None})(),
    )

    inspection = inspect_pipeline_state(material_id, novels_dir=tmp_path)

    assert inspection.legacy_unverified is True
    assert inspection.stages["insights"].status is RunStatus.DEGRADED
    assert inspection.stages["insights"].counts.failed == 2
    assert next_pending_stage(inspection) == "insights"
    assert not (novel_dir / "runs").exists()
