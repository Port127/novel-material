from pathlib import Path

from novel_material.infra.yaml_io import load_yaml, save_yaml
from novel_material.pipeline.work_profile import generate_work_profile


def test_generate_work_profile_reads_artifacts_and_writes_yaml(
    tmp_path: Path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "name": "示例"})
    save_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "主角创业"}])
    save_yaml(novel / "tags.yaml", {"themes": ["成长"]})
    (novel / "characters" / "profiles").mkdir(parents=True)
    save_yaml(
        novel / "characters" / "profiles" / "001_主角.yaml",
        {"name": "主角", "profile_level": "full"},
    )
    (novel / "worldbuilding" / "entities").mkdir(parents=True)
    save_yaml(
        novel / "worldbuilding" / "_index.yaml",
        {"layout": "layered", "llm_success": True},
    )
    save_yaml(
        novel / "worldbuilding" / "entities" / "organization_x.yaml",
        {
            "id": "organization_x",
            "type": "organization",
            "name": "公司",
            "description": "创业组织",
        },
    )

    monkeypatch.setattr("novel_material.pipeline.work_profile.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.pipeline.work_profile.load_config",
        lambda _provider=None: {"llm": {"profile_timeout": 1}},
    )
    monkeypatch.setattr(
        "novel_material.pipeline.work_profile.call_llm",
        lambda *_args, **_kwargs: {
            "core_hooks": ["创业逆袭"],
            "reader_expectations": ["成长爽点"],
            "story_structure": {
                "pacing_pattern": "阶段推进",
                "turning_point_pattern": [],
            },
            "character_dynamics": {
                "ensemble_summary": "围绕创业组队",
                "key_relationship_patterns": [],
            },
            "worldbuilding_drivers": [
                {
                    "mechanism": "商业竞争",
                    "narrative_function": "制造压力",
                }
            ],
            "motifs_and_techniques": ["日常细节"],
            "transferable_lessons": [
                {
                    "lesson": "用规则制造选择",
                    "applies_when": "现实题材",
                    "avoid_when": "规则缺失",
                }
            ],
            "evidence_index": {
                "chapters": [1],
                "characters": ["主角"],
                "worldbuilding_entities": ["organization_x"],
            },
            "limitations": [],
            "confidence": 0.8,
        },
    )

    assert generate_work_profile("nm_demo") is True

    profile = load_yaml(novel / "work_profile.yaml")
    assert profile["material_id"] == "nm_demo"
    assert profile["title"] == "示例"
    assert profile["evidence_index"]["chapters"] == [1]


def test_generate_work_profile_returns_false_without_required_facts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "nm_demo").mkdir()
    monkeypatch.setattr("novel_material.pipeline.work_profile.NOVELS_DIR", tmp_path)

    assert generate_work_profile("nm_demo") is False
    assert not (tmp_path / "nm_demo" / "work_profile.yaml").exists()
