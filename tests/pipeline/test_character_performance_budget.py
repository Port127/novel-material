from __future__ import annotations

from pathlib import Path
from time import perf_counter

from novel_material.infra.yaml_io import load_yaml, save_yaml
from novel_material.pipeline import characters_core


def _prepare_large_material(tmp_path: Path) -> Path:
    novels_dir = tmp_path / "novels"
    novel_dir = novels_dir / "nm_perf_characters"
    names = [f"角色{index:03d}" for index in range(1, 135)]
    save_yaml(
        novel_dir / "meta.yaml",
        {
            "material_id": "nm_perf_characters",
            "name": "性能预算素材",
            "status": "analyzed",
            "word_count": 2_000_000,
            "theme": ["都市"],
        },
    )
    save_yaml(
        novel_dir / "chapter_index.yaml",
        [
            {"chapter": chapter, "title": f"第 {chapter} 章", "type": "normal"}
            for chapter in range(1, 1085)
        ],
    )
    save_yaml(
        novel_dir / "evaluation.yaml",
        {
            "schema_version": "3.0.0",
            "novel_type": ["都市"],
            "premise": "大体量小说人物关系推进。",
            "main_thread_summary": "主角群在长篇叙事中持续推动主线。",
            "stage_map": [],
            "core_character_candidates": [
                {
                    "name": "角色120",
                    "reasons": ["前置导航候选"],
                    "confidence": 0.98,
                }
            ],
            "worldbuilding_dimensions": [],
            "analysis_focus": ["人物选择"],
            "sample_coverage": {},
        },
    )
    chapters = []
    for chapter in range(1, 1085):
        appeared = [
            name
            for index, name in enumerate(names, start=1)
            if chapter <= max(5, 139 - index)
        ]
        chapters.append(
            {
                "chapter": chapter,
                "title": f"第 {chapter} 章",
                "summary": "人物线索推进。",
                "characters_appear": appeared,
                "key_event": "角色001与角色120推动关键事件",
            }
        )
    save_yaml(novel_dir / "chapters.yaml", chapters)
    return novels_dir


def test_large_character_selection_and_report_budget_stays_local(
    tmp_path: Path,
    monkeypatch,
    record_property,
) -> None:
    novels_dir = _prepare_large_material(tmp_path)
    calls: list[tuple[str, list[str]]] = []

    def fake_extract(candidates, role_tier, *_args, **_kwargs):
        names = [name for name, _count in candidates]
        calls.append((role_tier, names))
        return [
            {
                "name": name,
                "role": "protagonist" if role_tier == "core" else role_tier,
                "description": f"{name}档案",
                "arc_summary": f"{name}弧线",
                "psychology": {"motivation": "推进主线"},
                "relationships": [],
                "key_events": [],
                "profile_level": "full" if role_tier == "core" else "brief",
                "biography_complete": role_tier == "core",
            }
            for name in names
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

    started = perf_counter()
    assert characters_core.generate_characters("nm_perf_characters") is True
    elapsed_seconds = perf_counter() - started

    record_property("baseline_type", "navigation_character_rules_only")
    record_property("character_budget_seconds", elapsed_seconds)

    index = load_yaml(
        novels_dir / "nm_perf_characters" / "characters" / "_index.yaml"
    )
    core_calls = [call for call in calls if call[0] == "core"]
    non_core_names = {
        name for role_tier, names in calls if role_tier != "core" for name in names
    }

    assert len(index["biography_targets"]) == index["biography_target_count"]
    assert 5 <= index["biography_target_count"] <= 12
    assert index["biography_completed_count"] == index["biography_target_count"]
    assert index["biography_failed_count"] == 0
    assert index["biography_selection_reason"] == "enough_candidates"
    assert len(core_calls) == 1
    assert len(core_calls[0][1]) == index["biography_target_count"]
    assert len(core_calls[0][1]) < 134
    assert non_core_names
    assert not set(core_calls[0][1]) & non_core_names
    assert elapsed_seconds < 2.0
