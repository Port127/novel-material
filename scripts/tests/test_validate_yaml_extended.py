"""
Extended tests for scripts/core/validate_yaml.py.

Covers gaps NOT in the existing test_validate_yaml.py:
  - validate_meta() — meta.yaml required fields + status validation
  - load_chapter_index() — various chapter_index.yaml formats
  - cmd_event() / cmd_meta() / cmd_all() — command-level orchestration
  - _flatten_event() — additional nested-to-flat edge cases
  - validate_event() — boundary conditions (tension exactly 1/5, None values)
"""

import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from core.validate_yaml import (
    validate_meta,
    validate_event,
    validate_yaml_parseable,
    load_chapter_index,
    load_tags_dict,
    _flatten_event,
    cmd_event,
    cmd_meta,
    cmd_all,
    META_REQUIRED_FIELDS,
)


TAGS_DICT_FIXTURE = {
    "event_type": {"description": "", "values": ["对决", "日常", "回忆"]},
    "conflict": {"description": "", "values": ["人与人", "人与命运"]},
    "stakes": {"description": "", "values": ["生死", "情感"]},
    "relationship": {"description": "", "values": ["师徒", "对手"]},
    "interaction": {"description": "", "values": ["对抗", "合作"]},
    "character_moment": {"description": "", "values": ["觉醒", "牺牲"]},
    "emotion": {"description": "", "values": ["燃", "悲伤", "温暖"]},
    "reader_effect": {"description": "", "values": ["催泪", "爽感"]},
    "plot_function": {"description": "", "values": ["推进主线", "铺垫"]},
    "plot_stage": {"description": "", "values": ["开端", "发展", "高潮"]},
    "technique": {"description": "", "values": ["伏笔", "反转"]},
    "dialogue_type": {"description": "", "values": ["争论", "独白"]},
    "info_delivery": {"description": "", "values": ["展示", "叙述"]},
    "setting": {"description": "", "values": ["战场", "城市"]},
    "time_weather": {"description": "", "values": ["黎明", "暴雨"]},
    "pacing": {"description": "", "values": ["快", "中", "慢"]},
    "pov": {"description": "", "values": ["第一人称", "第三人称限制"]},
    "power_dynamic": {"description": "", "values": ["以弱胜强", "势均力敌"]},
    "moral_spectrum": {"description": "", "values": ["正义", "灰色", "黑暗"]},
    "scale": {"description": "", "values": ["个人", "群体", "国家"]},
}


def _write_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)


def _make_valid_event():
    return {
        "id": "test_e1", "chapter": "第1章 测试", "title": "好标题",
        "summary": "摘要",
        "tension": 3,
        "event_type": ["对决"], "conflict": ["人与人"], "stakes": ["生死"],
        "relationship": ["对手"], "interaction": ["对抗"],
        "character_moment": ["觉醒"], "power_dynamic": "以弱胜强",
        "moral_spectrum": "正义", "plot_stage": "发展",
        "plot_function": ["推进主线"], "pacing": "快",
        "technique": ["伏笔"], "dialogue_type": ["争论"],
        "pov": "第三人称限制", "info_delivery": ["展示"],
        "setting": ["战场"], "scale": "个人",
        "time_weather": ["黎明"], "reader_effect": ["爽感"],
        "emotion": ["燃"],
        "characters": ["张三"],
    }


# ── validate_meta ─────────────────────────────────────────────────────


class TestValidateMeta:
    def test_valid_meta(self, tmp_path):
        meta = {
            "material_id": "nm_novel_20260101_test",
            "type": "novel", "name": "测试小说",
            "source": "source.txt", "status": "complete",
        }
        _write_yaml(tmp_path / "meta.yaml", meta)
        errors = validate_meta(tmp_path)
        assert errors == []

    def test_missing_required_fields(self, tmp_path):
        _write_yaml(tmp_path / "meta.yaml", {"material_id": "test"})
        errors = validate_meta(tmp_path)
        missing = [e for e in errors if "缺少必填字段" in e]
        assert len(missing) >= 3

    def test_invalid_status(self, tmp_path):
        meta = {
            "material_id": "x", "type": "novel", "name": "n",
            "source": "s", "status": "bogus_status",
        }
        _write_yaml(tmp_path / "meta.yaml", meta)
        errors = validate_meta(tmp_path)
        assert any("status 值无效" in e for e in errors)

    def test_valid_statuses_accepted(self, tmp_path):
        for st in ("raw", "outlined", "tagged", "complete", "refined"):
            meta = {
                "material_id": "x", "type": "novel", "name": "n",
                "source": "s", "status": st,
            }
            _write_yaml(tmp_path / "meta.yaml", meta)
            assert validate_meta(tmp_path) == []

    def test_meta_file_missing(self, tmp_path):
        errors = validate_meta(tmp_path)
        assert any("不存在" in e for e in errors)

    def test_meta_empty_file(self, tmp_path):
        (tmp_path / "meta.yaml").write_text("", encoding="utf-8")
        errors = validate_meta(tmp_path)
        assert len(errors) > 0

    def test_meta_unparseable_yaml(self, tmp_path):
        (tmp_path / "meta.yaml").write_text("{ bad: yaml: [", encoding="utf-8")
        errors = validate_meta(tmp_path)
        assert any("YAML" in e for e in errors)

    def test_empty_status_accepted(self, tmp_path):
        meta = {
            "material_id": "x", "type": "novel", "name": "n",
            "source": "s", "status": "",
        }
        _write_yaml(tmp_path / "meta.yaml", meta)
        errors = validate_meta(tmp_path)
        assert not any("status 值无效" in e for e in errors)


# ── load_chapter_index ────────────────────────────────────────────────


class TestLoadChapterIndex:
    def test_list_format(self, tmp_path):
        ci = [{"title": "第1章 起始"}, {"title": "第2章 转折"}]
        _write_yaml(tmp_path / "chapter_index.yaml", ci)
        titles = load_chapter_index(tmp_path)
        assert titles == {"第1章 起始", "第2章 转折"}

    def test_dict_with_chapters_key(self, tmp_path):
        ci = {"chapters": [{"title": "第1章 开始"}, {"title": "第2章 结束"}]}
        _write_yaml(tmp_path / "chapter_index.yaml", ci)
        titles = load_chapter_index(tmp_path)
        assert titles == {"第1章 开始", "第2章 结束"}

    def test_missing_file_returns_none(self, tmp_path):
        assert load_chapter_index(tmp_path) is None

    def test_empty_file_returns_none(self, tmp_path):
        (tmp_path / "chapter_index.yaml").write_text("", encoding="utf-8")
        assert load_chapter_index(tmp_path) is None

    def test_entries_without_title_ignored(self, tmp_path):
        ci = [{"title": "第1章"}, {"no_title": True}]
        _write_yaml(tmp_path / "chapter_index.yaml", ci)
        titles = load_chapter_index(tmp_path)
        assert titles == {"第1章"}


# ── _flatten_event (extra cases) ──────────────────────────────────────


class TestFlattenEventExtended:
    def test_event_id_renamed_to_id(self):
        raw = {"event_id": "e1", "chapter": "ch1", "title": "t", "summary": "s"}
        flat = _flatten_event(raw)
        assert flat["id"] == "e1"
        assert "event_id" not in flat

    def test_tension_extracted_from_nested_emotion(self):
        raw = {
            "id": "e1", "chapter": "c", "title": "t", "summary": "s",
            "emotion": {"tension": 4, "emotion": ["燃"]},
        }
        flat = _flatten_event(raw)
        assert flat["tension"] == 4

    def test_characters_dict_to_name_list(self):
        raw = {
            "id": "e1", "chapter": "c", "title": "t", "summary": "s",
            "characters": [{"name": "A"}, {"name": "B"}],
        }
        flat = _flatten_event(raw)
        assert flat["characters"] == ["A", "B"]

    def test_moral_spectrum_list_to_scalar(self):
        raw = {
            "id": "e1", "chapter": "c", "title": "t", "summary": "s",
            "moral_spectrum": ["正义"],
        }
        flat = _flatten_event(raw)
        assert flat["moral_spectrum"] == "正义"

    def test_moral_spectrum_empty_list(self):
        raw = {
            "id": "e1", "chapter": "c", "title": "t", "summary": "s",
            "moral_spectrum": [],
        }
        flat = _flatten_event(raw)
        assert flat["moral_spectrum"] == ""

    def test_nested_remap_location_to_setting(self):
        raw = {
            "id": "e1", "chapter": "c", "title": "t", "summary": "s",
            "setting": {"location": ["战场"], "time_weather": ["黎明"]},
        }
        flat = _flatten_event(raw)
        assert flat.get("setting") == ["战场"]

    def test_preserves_flat_format(self):
        event = _make_valid_event()
        flat = _flatten_event(event)
        assert flat["id"] == event["id"]
        assert flat["event_type"] == event["event_type"]


# ── validate_event (boundary cases) ──────────────────────────────────


class TestValidateEventBoundary:
    @pytest.fixture()
    def tags_dict(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir(exist_ok=True)
        _write_yaml(tmp_path / "data" / "tags.yaml", TAGS_DICT_FIXTURE)
        return {d: set(str(v) for v in info["values"])
                for d, info in TAGS_DICT_FIXTURE.items()}

    def test_tension_exactly_1_valid(self, tmp_path, tags_dict):
        event = _make_valid_event()
        event["tension"] = 1
        event_path = tmp_path / "event.yaml"
        _write_yaml(event_path, event)
        errors = validate_event(event_path, tags_dict, None)
        assert not any("tension" in e for e in errors)

    def test_tension_exactly_5_valid(self, tmp_path, tags_dict):
        event = _make_valid_event()
        event["tension"] = 5
        event_path = tmp_path / "event.yaml"
        _write_yaml(event_path, event)
        errors = validate_event(event_path, tags_dict, None)
        assert not any("tension" in e for e in errors)

    def test_tension_0_invalid(self, tmp_path, tags_dict):
        event = _make_valid_event()
        event["tension"] = 0
        event_path = tmp_path / "event.yaml"
        _write_yaml(event_path, event)
        errors = validate_event(event_path, tags_dict, None)
        assert any("tension" in e for e in errors)

    def test_tension_6_invalid(self, tmp_path, tags_dict):
        event = _make_valid_event()
        event["tension"] = 6
        event_path = tmp_path / "event.yaml"
        _write_yaml(event_path, event)
        errors = validate_event(event_path, tags_dict, None)
        assert any("tension" in e for e in errors)

    def test_none_tag_field_accepted(self, tmp_path, tags_dict):
        event = _make_valid_event()
        event["pov"] = None
        event_path = tmp_path / "event.yaml"
        _write_yaml(event_path, event)
        errors = validate_event(event_path, tags_dict, None)
        assert not any("pov 应为" in e for e in errors)

    def test_top_level_not_dict(self, tmp_path, tags_dict):
        event_path = tmp_path / "event.yaml"
        _write_yaml(event_path, ["not", "a", "dict"])
        errors = validate_event(event_path, tags_dict, None)
        assert any("顶层不是字典" in e for e in errors)

    def test_numeric_title_rejected(self, tmp_path, tags_dict):
        event = _make_valid_event()
        event["title"] = "事件42"
        event_path = tmp_path / "event.yaml"
        _write_yaml(event_path, event)
        errors = validate_event(event_path, tags_dict, None)
        assert any("无语义" in e for e in errors)

    def test_chapter_mismatch_detected(self, tmp_path, tags_dict):
        event = _make_valid_event()
        event["chapter"] = "不存在的章节"
        event_path = tmp_path / "event.yaml"
        _write_yaml(event_path, event)
        chapter_titles = {"第1章 测试", "第2章 进展"}
        errors = validate_event(event_path, tags_dict, chapter_titles)
        assert any("章节名不匹配" in e for e in errors)


# ── cmd_event / cmd_meta / cmd_all ────────────────────────────────────


class TestCommandFunctions:
    @pytest.fixture()
    def setup_material(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mid = "nm_test_cmd"
        base = tmp_path / "data" / "novels" / mid
        base.mkdir(parents=True)
        events = base / "events"
        events.mkdir()
        data_dir = tmp_path / "data"
        _write_yaml(data_dir / "tags.yaml", TAGS_DICT_FIXTURE)

        meta = {"material_id": mid, "type": "novel", "name": "N",
                "source": "s.txt", "status": "complete"}
        _write_yaml(base / "meta.yaml", meta)

        event = _make_valid_event()
        _write_yaml(events / "ev0001.yaml", event)
        return mid

    def test_cmd_event_pass(self, setup_material):
        assert cmd_event(setup_material) == 0

    def test_cmd_event_no_events_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data" / "novels" / "no_events").mkdir(parents=True)
        assert cmd_event("no_events") == 1

    def test_cmd_event_with_pattern(self, setup_material):
        assert cmd_event(setup_material, "ev0001") == 0

    def test_cmd_meta_pass(self, setup_material, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert cmd_meta(setup_material) == 0

    def test_cmd_meta_fail(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mid = "nm_test_bad_meta"
        base = tmp_path / "data" / "novels" / mid
        base.mkdir(parents=True)
        _write_yaml(base / "meta.yaml", {"material_id": mid})
        assert cmd_meta(mid) == 1

    def test_cmd_all_pass(self, setup_material, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert cmd_all(setup_material) == 0

    def test_cmd_all_missing_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert cmd_all("nonexistent_material") == 1

    def test_cmd_all_checks_optional_files(self, setup_material, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        base = tmp_path / "data" / "novels" / setup_material
        _write_yaml(base / "outline.yaml", {"premise": "test"})
        assert cmd_all(setup_material) == 0