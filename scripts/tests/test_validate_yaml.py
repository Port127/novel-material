"""Tests for validate_yaml.py."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from validate_yaml import validate_scene, validate_yaml_parseable, _flatten_scene, load_tags_dict


def _write_scene(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)


def _make_valid_scene():
    return {
        "id": "test_ch001_s1", "chapter": "第1章 起始", "title": "黎明之战",
        "summary": "精彩的战斗场景",
        "scene_type": ["对决"], "conflict": ["人与人"], "stakes": ["生死"],
        "relationship": ["对手"], "interaction": ["对抗"],
        "character_moment": ["觉醒"], "power_dynamic": "以弱胜强",
        "moral_spectrum": "正义", "emotion": ["燃"], "tension": 4,
        "reader_effect": ["爽感"], "plot_stage": "发展",
        "plot_function": ["推进主线"], "pacing": "快",
        "technique": ["伏笔"], "dialogue_type": ["争论"],
        "pov": "第三人称限制", "info_delivery": ["展示"],
        "setting": ["战场"], "scale": "个人", "time_weather": ["黎明"],
        "characters": ["张三"],
    }


class TestValidateScene:
    def test_valid_scene(self, novel_env):
        _, data_dir, novel_dir, _ = novel_env
        tags_dict = load_tags_dict()
        scene_path = novel_dir / "scenes" / "ch0001_s1.yaml"
        errs = validate_scene(scene_path, tags_dict, None)
        assert errs == []

    def test_missing_required_field(self, tmp_path, novel_env):
        _, data_dir, _, _ = novel_env
        scene = _make_valid_scene()
        del scene["id"]
        scene_path = tmp_path / "bad_scene.yaml"
        _write_scene(scene_path, scene)
        errs = validate_scene(scene_path, None, None)
        assert any("id" in e for e in errs)

    def test_invalid_tension(self, tmp_path):
        scene = _make_valid_scene()
        scene["tension"] = 8
        scene_path = tmp_path / "bad_tension.yaml"
        _write_scene(scene_path, scene)
        errs = validate_scene(scene_path, None, None)
        assert any("tension" in e for e in errs)

    def test_bad_title(self, tmp_path):
        scene = _make_valid_scene()
        scene["title"] = "场景1"
        scene_path = tmp_path / "bad_title.yaml"
        _write_scene(scene_path, scene)
        errs = validate_scene(scene_path, None, None)
        assert any("无语义" in e for e in errs)

    def test_illegal_tag_value(self, tmp_path, novel_env):
        _, data_dir, _, _ = novel_env
        tags_dict = load_tags_dict()
        scene = _make_valid_scene()
        scene["scene_type"] = ["不存在的标签"]
        scene_path = tmp_path / "illegal_tag.yaml"
        _write_scene(scene_path, scene)
        errs = validate_scene(scene_path, tags_dict, None)
        assert any("标签越界" in e for e in errs)

    def test_chapter_name_mismatch(self, tmp_path):
        scene = _make_valid_scene()
        scene_path = tmp_path / "mismatch.yaml"
        _write_scene(scene_path, scene)
        chapter_titles = {"第2章 别的标题"}
        errs = validate_scene(scene_path, None, chapter_titles)
        assert any("章节名不匹配" in e for e in errs)

    def test_unparseable_yaml(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text(": :\n  - [invalid yaml{{{", encoding="utf-8")
        errs = validate_scene(bad_file, None, None)
        assert any("YAML" in e for e in errs)

    def test_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("", encoding="utf-8")
        errs = validate_scene(empty_file, None, None)
        assert any("空" in e for e in errs)


class TestFlattenScene:
    def test_nested_format(self):
        nested = {
            "scene_id": "s1",
            "content": {"scene_type": ["对决"], "conflict": ["人与人"], "stakes": ["生死"]},
            "people": {"relationship": ["对手"], "power_dynamic": "强"},
        }
        flat = _flatten_scene(nested)
        assert flat["id"] == "s1"
        assert flat["scene_type"] == ["对决"]
        assert flat["power_dynamic"] == "强"


class TestValidateYamlParseable:
    def test_valid(self, tmp_path):
        f = tmp_path / "valid.yaml"
        f.write_text("key: value\n", encoding="utf-8")
        assert validate_yaml_parseable(f) == []

    def test_missing(self, tmp_path):
        f = tmp_path / "missing.yaml"
        errs = validate_yaml_parseable(f)
        assert len(errs) > 0

    def test_invalid(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(": [invalid{{{", encoding="utf-8")
        errs = validate_yaml_parseable(f)
        assert any("YAML" in e for e in errs)
