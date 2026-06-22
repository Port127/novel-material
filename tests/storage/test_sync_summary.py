"""数据库同步结果、批次汇总与修复授权测试。"""

from __future__ import annotations

from unittest.mock import Mock

from novel_material.runtime.contracts import RunStatus, StageResult
from novel_material.storage.sync_core import sync_all, sync_novel
from novel_material.storage.sync_utils import QualityCheckError


def sync_result(material_id: str, status: RunStatus) -> StageResult:
    return StageResult(
        stage_id=f"stage-sync-{material_id}",
        name="sync",
        status=status,
        outputs={"material_id": material_id},
    )


def test_sync_all_empty_directory_is_success(tmp_path):
    summary = sync_all(novels_dir=tmp_path, repair_allowed=False)

    assert summary.total == 0
    assert summary.succeeded == 0
    assert summary.failed == 0
    assert summary.status is RunStatus.SUCCESS


def test_sync_all_partial_failure_is_degraded(tmp_path, monkeypatch):
    for material_id in ("nm_ok", "nm_bad"):
        (tmp_path / material_id).mkdir()
    monkeypatch.setattr(
        "novel_material.storage.sync_core.sync_novel",
        lambda material_id, **_kwargs: sync_result(
            material_id,
            RunStatus.SUCCESS if material_id == "nm_ok" else RunStatus.FAILED,
        ),
    )

    summary = sync_all(novels_dir=tmp_path, repair_allowed=False)

    assert summary.total == 2
    assert summary.succeeded == 1
    assert summary.failed == 1
    assert summary.status is RunStatus.DEGRADED


def test_sync_does_not_repair_without_explicit_flag(tmp_path, monkeypatch):
    material_id = "nm_demo"
    (tmp_path / material_id).mkdir()
    repair = Mock()
    monkeypatch.setattr("novel_material.storage.sync_core.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.storage.sync_core._precheck_schema",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            QualityCheckError(material_id, short_chapters=[1])
        ),
    )
    monkeypatch.setattr(
        "novel_material.storage.sync_core.repair_short_summaries",
        repair,
    )

    result = sync_novel(material_id, repair_allowed=False)

    assert result.status is RunStatus.FAILED
    assert result.diagnostics[0].code == "sync_precheck_failed"
    repair.assert_not_called()
