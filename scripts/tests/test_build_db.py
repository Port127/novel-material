"""Tests for build_db.py."""

import sqlite3
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from build_db import create_schema, ingest_novel, _flatten_scene, _as_list, _str_or_first


class TestHelpers:
    def test_str_or_first_none(self):
        assert _str_or_first(None) == ""

    def test_str_or_first_string(self):
        assert _str_or_first("hello") == "hello"

    def test_str_or_first_list(self):
        assert _str_or_first(["a", "b"]) == "a, b"

    def test_str_or_first_empty_list(self):
        assert _str_or_first([]) == ""

    def test_as_list_none(self):
        assert _as_list(None) == []

    def test_as_list_string(self):
        assert _as_list("hello") == ["hello"]

    def test_as_list_list(self):
        assert _as_list(["a", "b"]) == ["a", "b"]

    def test_as_list_dict_ignored(self):
        assert _as_list({"name": "x"}) == []


class TestFlattenScene:
    def test_flat_passthrough(self):
        scene = {"id": "s1", "scene_type": ["对决"], "tension": 3}
        flat = _flatten_scene(scene)
        assert flat["id"] == "s1"
        assert flat["scene_type"] == ["对决"]

    def test_nested_to_flat(self):
        scene = {
            "scene_id": "s1",
            "content": {"scene_type": ["对决"], "conflict": ["人与人"], "stakes": ["生死"]},
            "people": {"relationship": ["对手"], "power_dynamic": "以弱胜强"},
            "emotion": {"emotion": ["燃"], "tension": 4, "reader_effect": ["爽感"]},
        }
        flat = _flatten_scene(scene)
        assert flat["id"] == "s1"
        assert flat["scene_type"] == ["对决"]
        assert flat["power_dynamic"] == "以弱胜强"
        assert flat["tension"] == 4

    def test_moral_spectrum_list_to_scalar(self):
        scene = {"moral_spectrum": ["正义", "灰色"]}
        flat = _flatten_scene(scene)
        assert flat["moral_spectrum"] == "正义"

    def test_characters_dict_to_names(self):
        scene = {"characters": [{"name": "张三"}, {"name": "李四"}]}
        flat = _flatten_scene(scene)
        assert flat["characters"] == ["张三", "李四"]


class TestIngestNovel:
    def test_ingest(self, novel_env):
        tmp_path, data_dir, novel_dir, mid = novel_env
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)

        count = ingest_novel(conn, mid)
        assert count == 10

        row = conn.execute("SELECT * FROM novels WHERE material_id=?", (mid,)).fetchone()
        assert row is not None

        scenes = conn.execute("SELECT COUNT(*) FROM scenes WHERE material_id=?", (mid,)).fetchone()[0]
        assert scenes == 10

        tags = conn.execute("SELECT COUNT(*) FROM scene_tags WHERE material_id=?", (mid,)).fetchone()[0]
        assert tags > 0

        chars = conn.execute("SELECT COUNT(*) FROM characters WHERE material_id=?", (mid,)).fetchone()[0]
        assert chars == 2

        sc = conn.execute("SELECT COUNT(*) FROM scene_characters").fetchone()[0]
        assert sc > 0

        conn.close()

    def test_ingest_missing_dir(self, novel_env):
        tmp_path, data_dir, novel_dir, mid = novel_env
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)

        count = ingest_novel(conn, "nonexistent_id")
        assert count == 0
        conn.close()

    def test_reingest_clears_old_data(self, novel_env):
        tmp_path, data_dir, novel_dir, mid = novel_env
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)

        ingest_novel(conn, mid)
        ingest_novel(conn, mid)

        novels = conn.execute("SELECT COUNT(*) FROM novels WHERE material_id=?", (mid,)).fetchone()[0]
        assert novels == 1

        conn.close()
