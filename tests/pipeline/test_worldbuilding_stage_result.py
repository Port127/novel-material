from pathlib import Path

from novel_material.infra.yaml_io import save_yaml
from novel_material.pipeline.worldbuilding import generate_worldbuilding
from novel_material.runtime.contracts import RunStatus, StageResult


def test_worldbuilding_empty_fallback_is_degraded(
    tmp_path: Path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "name": "示例"})
    save_yaml(novel / "chapter_index.yaml", [{"chapter": 1, "title": "一"}])
    save_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "公司竞争"}])

    monkeypatch.setattr("novel_material.pipeline.worldbuilding.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.load_config",
        lambda _provider=None: {
            "llm": {
                "worldbuilding_timeout": 1,
                "rate_limit_seconds": 0,
                "worldbuilding_summary_tokens": 1000,
            }
        },
    )
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.call_llm",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("api down")),
    )
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.build_analysis_context",
        lambda *_args, **_kwargs: ("第1章：公司竞争", "章级摘要池"),
    )

    result = generate_worldbuilding("nm_demo")

    assert isinstance(result, StageResult)
    assert result.status is RunStatus.DEGRADED
    assert result.outputs["llm_success"] is False
    assert result.outputs["entity_count"] == 0
    assert result.diagnostics[0].code == "worldbuilding_api_failed"
