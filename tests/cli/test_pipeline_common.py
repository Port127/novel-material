"""完整流水线统一阶段计划测试。"""

from novel_material.cli import pipeline_common
from novel_material.pipeline.orchestrator import RunRequest
from novel_material.runtime.contracts import RunStatus, StageResult


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
