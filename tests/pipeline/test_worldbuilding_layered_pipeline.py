from pathlib import Path

from novel_material.infra.yaml_io import load_yaml, save_yaml
from novel_material.pipeline.worldbuilding import generate_worldbuilding
from novel_material.pipeline.worldbuilding_fallback import build_stats_seeded_entities
from novel_material.pipeline.worldbuilding_jobs import build_worldbuilding_jobs
from novel_material.runtime.contracts import RunStatus, StageResult


def test_generate_worldbuilding_writes_layered_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(
        novel / "meta.yaml",
        {"material_id": "nm_demo", "name": "示例", "genre": ["都市"]},
    )
    save_yaml(novel / "chapter_index.yaml", [{"chapter": 1, "title": "开篇"}])
    save_yaml(
        novel / "chapters.yaml",
        [
            {
                "chapter": 1,
                "summary": "学生会推动校园冲突",
                "characters_appear": ["学生会成员"],
                "setting": ["江陵大学"],
            }
        ],
    )
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
        "novel_material.pipeline.worldbuilding.build_analysis_context",
        lambda *_args, **_kwargs: ("第1章：学生会推动校园冲突", "章级摘要池"),
    )
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.call_llm",
        lambda *_args, **_kwargs: {
            "overview": {
                "world_summary": "校园组织关系驱动剧情",
                "driving_mechanisms": [],
            },
            "dimensions": [],
            "entities": [
                {
                    "type": "organization",
                    "name": "学生会",
                    "description": "校园组织",
                    "importance": "secondary",
                    "evidence": [{"chapter": 1, "basis": "fact", "summary": "出现"}],
                }
            ],
            "relations": [],
        },
    )

    result = generate_worldbuilding("nm_demo")

    assert isinstance(result, StageResult)
    assert result.status is RunStatus.SUCCESS
    assert result.outputs["llm_success"] is True
    assert result.outputs["entity_count"] == 1

    index = load_yaml(novel / "worldbuilding" / "_index.yaml")
    assert index["layout"] == "layered"
    assert index["entity_count"] == 1
    assert (novel / "worldbuilding" / "overview.yaml").is_file()
    assert (novel / "worldbuilding" / "dimensions.yaml").is_file()
    assert len(list((novel / "worldbuilding" / "entities").glob("*.yaml"))) == 1
    assert (novel / "worldbuilding" / "relations.yaml").is_file()


def test_generate_worldbuilding_writes_empty_layered_outputs_on_llm_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(
        novel / "meta.yaml",
        {"material_id": "nm_demo", "name": "示例", "genre": ["都市"]},
    )
    save_yaml(novel / "chapter_index.yaml", [{"chapter": 1, "title": "开篇"}])
    save_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "现实创业"}])
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
        "novel_material.pipeline.worldbuilding.build_analysis_context",
        lambda *_args, **_kwargs: ("第1章：现实创业", "章级摘要池"),
    )
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.call_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = generate_worldbuilding("nm_demo")

    assert isinstance(result, StageResult)
    assert result.status is RunStatus.DEGRADED
    assert result.outputs["llm_success"] is False
    assert result.diagnostics[0].code == "worldbuilding_api_failed"

    index = load_yaml(novel / "worldbuilding" / "_index.yaml")
    dimensions = load_yaml(novel / "worldbuilding" / "dimensions.yaml")
    assert index["layout"] == "layered"
    assert index["llm_success"] is False
    assert index["entity_count"] == 0
    assert dimensions["dimensions"]


def test_build_worldbuilding_jobs_uses_applicable_dimensions_only():
    dimensions = [
        {"id": "organizations", "applicability": "applicable", "name": "组织"},
        {"id": "power_system", "applicability": "not_applicable", "name": "力量体系"},
    ]

    jobs = build_worldbuilding_jobs(
        dimensions,
        context_text="摘要",
        context_label="章级摘要池",
    )

    assert [job.dimension_id for job in jobs] == ["organizations"]
    assert jobs[0].context_text == "摘要"
    assert jobs[0].context_label == "章级摘要池"


def test_build_stats_seeded_entities_creates_conservative_entities():
    stats = {
        "organizations": {"黑星军团": 12},
        "locations": {"海蓝星": 7},
    }

    entities = build_stats_seeded_entities(stats, min_count=5)

    by_name = {entity["name"]: entity for entity in entities}
    assert by_name["黑星军团"]["source_quality"] == "stats_seeded"
    assert by_name["黑星军团"]["type"] == "organization"
    assert by_name["海蓝星"]["type"] == "location"
    assert by_name["海蓝星"]["confidence"] == 0.45


def test_worldbuilding_dimension_failure_keeps_successful_dimension(
    tmp_path: Path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(
        novel / "meta.yaml",
        {"material_id": "nm_demo", "name": "示例", "genre": ["科幻"]},
    )
    save_yaml(novel / "chapter_index.yaml", [{"chapter": 1, "title": "一"}])
    save_yaml(
        novel / "chapters.yaml",
        [
            {
                "chapter": 1,
                "summary": "黑星军团在海蓝星行动",
                "characters_appear": ["黑星军团成员"],
                "setting": ["海蓝星"],
            }
        ],
    )

    calls = []

    def fake_call_llm(*_args, **kwargs):
        calls.append(kwargs.get("context", ""))
        if "locations" in kwargs.get("context", ""):
            raise RuntimeError("timeout")
        return {
            "overview": {"world_summary": "组织推动剧情", "driving_mechanisms": []},
            "dimensions": [],
            "entities": [
                {
                    "type": "organization",
                    "name": "黑星军团",
                    "description": "核心组织",
                    "importance": "primary",
                    "evidence": [{"chapter": 1, "basis": "fact", "summary": "出现"}],
                }
            ],
            "relations": [],
        }

    monkeypatch.setattr("novel_material.pipeline.worldbuilding.NOVELS_DIR", tmp_path)
    monkeypatch.setattr("novel_material.pipeline.worldbuilding.call_llm", fake_call_llm)
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
        "novel_material.pipeline.worldbuilding.build_analysis_context",
        lambda *_args, **_kwargs: ("黑星军团在海蓝星行动", "章级摘要池"),
    )

    result = generate_worldbuilding("nm_demo")

    assert calls
    assert result.status.value in {"success", "degraded"}
    assert result.outputs["entity_count"] >= 1
    assert result.outputs["dimension_status"]["locations"] in {"stats_seeded", "missing"}
