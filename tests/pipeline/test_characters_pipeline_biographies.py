"""characters 阶段完整小传接入测试。"""

import hashlib
from pathlib import Path

from novel_material.infra.yaml_io import load_yaml, save_yaml
from novel_material.pipeline import characters_core


def _prepare_material(tmp_path: Path, names: list[str]) -> Path:
    novels_dir = tmp_path / "novels"
    novel_dir = novels_dir / "nm_demo"
    save_yaml(
        novel_dir / "meta.yaml",
        {
            "material_id": "nm_demo",
            "name": "测试小说",
            "status": "analyzed",
            "word_count": 10000,
            "theme": ["都市"],
        },
    )
    save_yaml(
        novel_dir / "chapter_index.yaml",
        [{"chapter": index, "title": f"第{index}章"} for index in range(1, 7)],
    )
    save_yaml(
        novel_dir / "evaluation.yaml",
        {
            "schema_version": "3.0.0",
            "novel_type": ["都市"],
            "premise": "主角重新选择人生。",
            "main_thread_summary": "主角围绕事业与关系重新做选择。",
            "stage_map": [],
            "core_character_candidates": [
                {"name": names[-1], "reasons": ["前置导航候选"], "confidence": 0.99}
            ],
            "worldbuilding_dimensions": [],
            "analysis_focus": ["人物选择"],
            "sample_coverage": {},
        },
    )
    chapters = []
    for chapter in range(1, 7):
        chapters.append(
            {
                "chapter": chapter,
                "title": f"第{chapter}章",
                "summary": "人物关系推进。",
                "characters_appear": names,
                "key_event": f"{names[0]}和{names[-1]}共同推进事件",
            }
        )
    save_yaml(novel_dir / "chapters.yaml", chapters)
    return novels_dir


def test_characters_stage_generates_full_biographies_only_for_targets(
    tmp_path,
    monkeypatch,
):
    names = [f"角色{i}" for i in range(1, 14)]
    novels_dir = _prepare_material(tmp_path, names)
    calls: list[tuple[str, list[str]]] = []

    def fake_extract(candidates, role_tier, *_args, **_kwargs):
        calls.append((role_tier, [name for name, _count in candidates]))
        return [
            {
                "name": name,
                "role": "supporting" if role_tier != "minor" else "minor",
                "description": f"{name}档案",
                "arc_summary": f"{name}弧线",
                "psychology": {"motivation": "测试"},
                "relationships": [],
                "key_events": [],
                "profile_level": "full" if role_tier == "core" else "brief",
                "biography_complete": role_tier == "core",
            }
            for name, _count in candidates
        ]

    monkeypatch.setattr(characters_core, "NOVELS_DIR", novels_dir)
    monkeypatch.setattr(characters_core, "load_config", lambda _provider=None: {"llm": {}})
    monkeypatch.setattr(characters_core, "build_analysis_context", lambda *_args, **_kwargs: ("上下文", "摘要池"))
    monkeypatch.setattr(characters_core, "start_llm_telemetry", lambda: type("Telemetry", (), {"details": []})())
    monkeypatch.setattr(characters_core, "_extract_character_batch", fake_extract)

    assert characters_core.generate_characters("nm_demo") is True

    core_call = next(call for call in calls if call[0] == "core")
    brief_calls = [call for call in calls if call[0] != "core"]
    assert 5 <= len(core_call[1]) <= 12
    assert names[-1] in core_call[1]
    assert any(set(call[1]) - set(core_call[1]) for call in brief_calls)

    profiles = [
        load_yaml(path)
        for path in (novels_dir / "nm_demo" / "characters" / "profiles").glob("*.yaml")
    ]
    full_profiles = [item for item in profiles if item.get("profile_level") == "full"]
    brief_profiles = [item for item in profiles if item.get("profile_level") == "brief"]
    assert len(full_profiles) == len(core_call[1])
    assert brief_profiles
    assert all(item["biography_complete"] is False for item in brief_profiles)


def test_characters_index_records_biography_selection_metadata(
    tmp_path,
    monkeypatch,
):
    names = [f"角色{i}" for i in range(1, 7)]
    novels_dir = _prepare_material(tmp_path, names)

    def fake_extract(candidates, role_tier, *_args, **_kwargs):
        return [
            {
                "name": name,
                "role": "supporting",
                "description": f"{name}档案",
                "relationships": [],
                "key_events": [],
                "profile_level": "full" if role_tier == "core" else "brief",
                "biography_complete": role_tier == "core",
            }
            for name, _count in candidates
        ]

    monkeypatch.setattr(characters_core, "NOVELS_DIR", novels_dir)
    monkeypatch.setattr(characters_core, "load_config", lambda _provider=None: {"llm": {}})
    monkeypatch.setattr(characters_core, "build_analysis_context", lambda *_args, **_kwargs: ("上下文", "摘要池"))
    monkeypatch.setattr(characters_core, "start_llm_telemetry", lambda: type("Telemetry", (), {"details": []})())
    monkeypatch.setattr(characters_core, "_extract_character_batch", fake_extract)

    assert characters_core.generate_characters("nm_demo") is True

    index = load_yaml(novels_dir / "nm_demo" / "characters" / "_index.yaml")
    assert index["biography_target_count"] == 6
    assert index["biography_completed_count"] == 6
    assert index["biography_failed_count"] == 0
    assert index["biography_selection_reason"] == "enough_candidates"
    assert len(index["biography_targets"]) == 6
    assert {"name", "score", "reasons"} <= set(index["biography_targets"][0])


def test_repair_characters_only_rebuilds_requested_profile(tmp_path, monkeypatch):
    names = ["甲", "乙", "丙"]
    novels_dir = _prepare_material(tmp_path, names)
    profiles_dir = novels_dir / "nm_demo" / "characters" / "profiles"
    save_yaml(
        profiles_dir / "甲_000.yaml",
        {
            "name": "甲",
            "role": "supporting",
            "description": "旧甲",
            "relationships": [],
            "biography_complete": False,
        },
    )
    save_yaml(
        profiles_dir / "乙_001.yaml",
        {
            "name": "乙",
            "role": "supporting",
            "description": "旧乙",
            "relationships": [],
            "biography_complete": False,
        },
    )
    save_yaml(
        profiles_dir / "丙_002.yaml",
        {
            "name": "丙",
            "role": "minor",
            "description": "旧丙",
            "relationships": [],
            "biography_complete": False,
        },
    )
    before_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(profiles_dir.glob("*.yaml"))
    }
    calls: list[list[str]] = []

    def fake_extract(candidates, role_tier, *_args, **_kwargs):
        calls.append([name for name, _count in candidates])
        return [
            {
                "name": name,
                "role": "supporting",
                "description": "新甲",
                "arc_summary": "重建小传",
                "psychology": {"motivation": "修复"},
                "relationships": [],
                "key_events": [],
                "profile_level": "full",
                "biography_complete": True,
            }
            for name, _count in candidates
        ]

    monkeypatch.setattr(characters_core, "NOVELS_DIR", novels_dir)
    monkeypatch.setattr(characters_core, "load_config", lambda _provider=None: {"llm": {}})
    monkeypatch.setattr(
        characters_core,
        "build_analysis_context",
        lambda *_args, **_kwargs: ("上下文", "摘要池"),
    )
    monkeypatch.setattr(
        characters_core,
        "start_llm_telemetry",
        lambda: type("Telemetry", (), {"details": []})(),
    )
    monkeypatch.setattr(characters_core, "_extract_character_batch", fake_extract)

    assert characters_core.generate_characters(
        "nm_demo",
        repair_characters=("甲",),
    ) is True

    assert calls == [["甲"]]
    after_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(profiles_dir.glob("*.yaml"))
    }
    assert after_hashes["乙_001.yaml"] == before_hashes["乙_001.yaml"]
    assert after_hashes["丙_002.yaml"] == before_hashes["丙_002.yaml"]
    repaired_profiles = [
        load_yaml(path)
        for path in profiles_dir.glob("*.yaml")
        if load_yaml(path).get("name") == "甲"
    ]
    assert len(repaired_profiles) == 1
    assert repaired_profiles[0]["description"] == "新甲"
    assert repaired_profiles[0]["biography_complete"] is True
    index = load_yaml(novels_dir / "nm_demo" / "characters" / "_index.yaml")
    assert index["repair_requested"] is True
