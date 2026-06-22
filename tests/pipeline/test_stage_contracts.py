"""Pipeline 旧返回值到 StageResult 的严格过渡契约。"""

from __future__ import annotations

from novel_material.pipeline.stage_contracts import adapt_stage_result
from novel_material.pipeline import stages as stage_entries
from novel_material.runtime.contracts import RunStatus, StageResult


def test_false_and_none_are_failed_not_success():
    assert adapt_stage_result("analyze", False).status is RunStatus.FAILED
    assert adapt_stage_result("analyze", None).status is RunStatus.FAILED


def test_ingest_string_is_explicit_material_output():
    result = adapt_stage_result("ingest", "nm_demo", output_key="material_id")

    assert result.status is RunStatus.SUCCESS
    assert result.outputs == {"material_id": "nm_demo"}


def test_existing_stage_result_is_not_reinterpreted():
    source = StageResult(
        stage_id="stage-1",
        name="insights",
        status=RunStatus.DEGRADED,
    )

    assert adapt_stage_result("insights", source) is source


def test_ingest_stage_entry_returns_material_output(monkeypatch):
    monkeypatch.setattr(stage_entries, "ingest_file", lambda *_args, **_kwargs: "nm_demo")

    result = stage_entries.run_ingest_stage("novel.txt")

    assert result.status is RunStatus.SUCCESS
    assert result.outputs["material_id"] == "nm_demo"


def test_boolean_stage_entry_never_returns_bool(monkeypatch):
    monkeypatch.setattr(stage_entries, "generate_outline", lambda *_args, **_kwargs: False)

    result = stage_entries.run_outline_stage("nm_demo")

    assert isinstance(result, StageResult)
    assert result.status is RunStatus.FAILED
