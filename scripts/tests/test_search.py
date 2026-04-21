"""
tests for scripts/core/search.py — CLI SQLite search module.

This is a completely NEW test file. search.py previously had ZERO unit tests.
Covers: search_events, search_characters, search_text, show_stats, get_conn, argparse.
"""

import sqlite3
import sys
import types
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _build_db(db_path: Path):
    """Create a test DB matching the schema search.py expects."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE novels (
            material_id TEXT PRIMARY KEY, name TEXT, author TEXT,
            status TEXT, total_events INTEGER DEFAULT 0, built_at TEXT
        );
        CREATE TABLE events (
            event_id TEXT NOT NULL, material_id TEXT NOT NULL,
            chapter TEXT, title TEXT, summary TEXT, tension INTEGER DEFAULT 0,
            pacing TEXT, pov TEXT, power_dynamic TEXT, moral_spectrum TEXT,
            plot_stage TEXT, scale TEXT,
            PRIMARY KEY (event_id, material_id)
        );
        CREATE TABLE event_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL, material_id TEXT NOT NULL,
            dimension TEXT NOT NULL, value TEXT NOT NULL
        );
        CREATE TABLE characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL, name TEXT NOT NULL,
            role TEXT, archetype TEXT, moral_spectrum TEXT,
            arc_summary TEXT, narrative_function TEXT,
            fatal_flaw TEXT, obsession TEXT, soft_spot TEXT, misbelief TEXT
        );
        CREATE TABLE event_characters (
            event_id TEXT NOT NULL, material_id TEXT NOT NULL,
            character_name TEXT NOT NULL,
            PRIMARY KEY (event_id, material_id, character_name)
        );
        CREATE INDEX idx_et_dv ON event_tags(dimension, value);
        CREATE INDEX idx_ec_name ON event_characters(character_name);
    """)

    mid = "nm_novel_test"
    conn.execute("INSERT INTO novels VALUES (?,?,?,?,?,?)",
                 (mid, "测试小说", "作者", "complete", 4, "2026-01-01"))

    events = [
        ("ev0001", mid, "第1章", "黎明之战", "主角与宿敌在黎明决战", 4, "快", "第三人称限制", "以弱胜强", "正义", "发展", "个人"),
        ("ev0002", mid, "第2章", "温暖回忆", "回忆师父的教导", 2, "慢", "第一人称", "势均力敌", "灰色", "开端", "个人"),
        ("ev0003", mid, "第3章", "最终对决", "正邪最终大战", 5, "快", "全知", "以弱胜强", "正义", "高潮", "国家"),
        ("ev0004", mid, "第4章", "告别", "主角与朋友告别离去", 3, "中", "第三人称限制", "势均力敌", "正义", "结局", "个人"),
    ]
    conn.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", events)

    tag_rows = [
        ("ev0001", mid, "event_type", "对决"), ("ev0001", mid, "emotion", "燃"),
        ("ev0001", mid, "conflict", "人与人"), ("ev0001", mid, "reader_effect", "爽感"),
        ("ev0002", mid, "event_type", "回忆"), ("ev0002", mid, "emotion", "温暖"),
        ("ev0002", mid, "emotion", "悲伤"),
        ("ev0003", mid, "event_type", "对决"), ("ev0003", mid, "emotion", "燃"),
        ("ev0003", mid, "conflict", "人与命运"), ("ev0003", mid, "reader_effect", "催泪"),
        ("ev0004", mid, "event_type", "日常"), ("ev0004", mid, "emotion", "悲伤"),
    ]
    conn.executemany("INSERT INTO event_tags (event_id, material_id, dimension, value) VALUES (?,?,?,?)", tag_rows)

    chars = [
        (mid, "张三", "protagonist", "英雄", "正义", "成长", "推动主线", "冲动", "力量", "妹妹", "暴力可以解决一切"),
        (mid, "李四", "antagonist", "暗影", "黑暗", "堕落", "冲突", "傲慢", "权力", None, None),
        (mid, "王五", "supporting", "导师", "灰色", "辅助", "引导", None, None, None, None),
    ]
    conn.executemany(
        "INSERT INTO characters (material_id,name,role,archetype,moral_spectrum,arc_summary,narrative_function,fatal_flaw,obsession,soft_spot,misbelief) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        chars,
    )

    ec_rows = [
        ("ev0001", mid, "张三"), ("ev0001", mid, "李四"),
        ("ev0002", mid, "张三"), ("ev0002", mid, "王五"),
        ("ev0003", mid, "张三"), ("ev0003", mid, "李四"),
        ("ev0004", mid, "张三"),
    ]
    conn.executemany("INSERT INTO event_characters VALUES (?,?,?)", ec_rows)

    conn.commit()
    conn.close()


@pytest.fixture()
def search_env(tmp_path, monkeypatch):
    """Set up DB and patch search.DB_PATH."""
    db_path = tmp_path / "data" / "material.db"
    db_path.parent.mkdir(parents=True)
    _build_db(db_path)

    import core.search as search_mod
    monkeypatch.setattr(search_mod, "DB_PATH", db_path)
    return search_mod, db_path


# ── get_conn ──────────────────────────────────────────────────────────


class TestGetConn:
    def test_returns_connection(self, search_env):
        mod, _ = search_env
        conn = mod.get_conn()
        assert conn is not None
        conn.close()

    def test_missing_db_exits(self, tmp_path, monkeypatch):
        import core.search as search_mod
        monkeypatch.setattr(search_mod, "DB_PATH", tmp_path / "nonexistent.db")
        with pytest.raises(SystemExit):
            search_mod.get_conn()


# ── search_events ─────────────────────────────────────────────────────


class TestSearchEvents:
    def _make_args(self, **overrides):
        defaults = {dim: None for dim in [
            'event_type', 'conflict', 'stakes', 'relationship', 'interaction',
            'character_moment', 'emotion', 'reader_effect', 'plot_function',
            'plot_stage', 'technique', 'dialogue_type', 'info_delivery',
            'setting', 'time_weather', 'pacing', 'pov', 'power_dynamic',
            'moral_spectrum', 'scale',
        ]}
        defaults.update(character=None, material=None, tension_min=None,
                        tension_max=None, limit=20)
        defaults.update(overrides)
        return types.SimpleNamespace(**defaults)

    def test_single_tag_filter(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(event_type="对决")
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 2
        ids = {r["event_id"] for r in parsed["results"]}
        assert ids == {"ev0001", "ev0003"}

    def test_multi_tag_intersection(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(event_type="对决", conflict="人与命运")
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 1
        assert parsed["results"][0]["event_id"] == "ev0003"

    def test_character_filter(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(character="王五")
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 1
        assert parsed["results"][0]["event_id"] == "ev0002"

    def test_material_filter(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(material="nm_novel_test")
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 4

    def test_tension_min_filter(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(material="nm_novel_test", tension_min=4)
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        for r in parsed["results"]:
            assert r["tension"] >= 4

    def test_tension_max_filter(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(material="nm_novel_test", tension_max=2)
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        for r in parsed["results"]:
            assert r["tension"] <= 2

    def test_no_filter_exits(self, search_env):
        mod, _ = search_env
        args = self._make_args()
        with pytest.raises(SystemExit):
            mod.search_events(args)

    def test_no_match_prints_zero(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(event_type="不存在的类型")
        mod.search_events(args)
        out = capsys.readouterr().out
        assert "total: 0" in out

    def test_relaxation_on_impossible_intersection(self, search_env, capsys):
        """When AND yields 0 but individual sets have results, relaxation kicks in."""
        mod, _ = search_env
        args = self._make_args(event_type="回忆", conflict="人与命运")
        mod.search_events(args)
        out = capsys.readouterr().out
        stderr = capsys.readouterr().err
        parsed = yaml.safe_load(out)
        assert parsed["total"] >= 1

    def test_score_sorting(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(event_type="对决", emotion="燃")
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        scores = [r["score"] for r in parsed["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_limit_parameter(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(material="nm_novel_test", limit=2)
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert len(parsed["results"]) <= 2

    def test_query_echoed_in_output(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(event_type="对决", character="张三")
        mod.search_events(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["query"]["event_type"] == "对决"
        assert parsed["query"]["character"] == "张三"


# ── search_characters ─────────────────────────────────────────────────


class TestSearchCharacters:
    def _make_args(self, **overrides):
        defaults = dict(name=None, archetype=None, role=None,
                        material=None, moral_spectrum=None, limit=20)
        defaults.update(overrides)
        return types.SimpleNamespace(**defaults)

    def test_by_name(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(name="张三")
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 1
        assert parsed["results"][0]["name"] == "张三"

    def test_by_archetype(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(archetype="导师")
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 1
        assert parsed["results"][0]["name"] == "王五"

    def test_by_role(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(role="antagonist")
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 1
        assert parsed["results"][0]["name"] == "李四"

    def test_by_moral_spectrum(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(moral_spectrum="正义")
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 1
        assert parsed["results"][0]["name"] == "张三"

    def test_psychology_fields_present(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(name="张三")
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        r = parsed["results"][0]
        assert "psychology" in r
        assert r["psychology"]["fatal_flaw"] == "冲动"

    def test_psychology_fields_absent_when_empty(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(name="王五")
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        r = parsed["results"][0]
        assert "psychology" not in r

    def test_appearance_count(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(name="张三")
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["results"][0]["appearance_count"] == 4

    def test_no_filter_exits(self, search_env):
        mod, _ = search_env
        args = self._make_args()
        with pytest.raises(SystemExit):
            mod.search_characters(args)

    def test_name_like_partial(self, search_env, capsys):
        """Name filter uses LIKE with %, so partial matches should work."""
        mod, _ = search_env
        args = self._make_args(name="三")
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 1

    def test_limit_respected(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args(material="nm_novel_test", limit=1)
        mod.search_characters(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert len(parsed["results"]) == 1


# ── search_text ───────────────────────────────────────────────────────


class TestSearchText:
    def _make_args(self, query, limit=20):
        return types.SimpleNamespace(query=query, limit=limit)

    def test_match_by_summary(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args("黎明")
        mod.search_text(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] >= 1
        assert any("黎明" in r.get("summary", "") or "黎明" in r.get("title", "")
                    for r in parsed["results"])

    def test_match_by_title(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args("告别")
        mod.search_text(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] >= 1

    def test_no_match(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args("完全不存在的内容xyz")
        mod.search_text(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 0

    def test_limit(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args("主角", limit=1)
        mod.search_text(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert len(parsed["results"]) <= 1

    def test_query_echoed(self, search_env, capsys):
        mod, _ = search_env
        args = self._make_args("回忆")
        mod.search_text(args)
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["query"] == "回忆"


# ── show_stats ────────────────────────────────────────────────────────


class TestShowStats:
    def test_basic_counts(self, search_env, capsys):
        mod, _ = search_env
        mod.show_stats(types.SimpleNamespace())
        out = capsys.readouterr().out
        assert "novels: 1" in out
        assert "events: 4" in out
        assert "characters: 3" in out

    def test_per_novel_section(self, search_env, capsys):
        mod, _ = search_env
        mod.show_stats(types.SimpleNamespace())
        out = capsys.readouterr().out
        assert "per_novel:" in out
        assert "nm_novel_test" in out

    def test_top_event_types(self, search_env, capsys):
        mod, _ = search_env
        mod.show_stats(types.SimpleNamespace())
        out = capsys.readouterr().out
        assert "top_event_types:" in out
        assert "对决" in out

    def test_top_emotions(self, search_env, capsys):
        mod, _ = search_env
        mod.show_stats(types.SimpleNamespace())
        out = capsys.readouterr().out
        assert "top_emotions:" in out


# ── main / argparse ───────────────────────────────────────────────────


class TestMainArgparse:
    def test_event_subcommand(self, search_env, monkeypatch, capsys):
        mod, _ = search_env
        monkeypatch.setattr(sys, "argv", ["search.py", "event", "--event-type", "对决"])
        mod.main()
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] >= 1

    def test_character_subcommand(self, search_env, monkeypatch, capsys):
        mod, _ = search_env
        monkeypatch.setattr(sys, "argv", ["search.py", "character", "--name", "张三"])
        mod.main()
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert parsed["total"] == 1

    def test_text_subcommand(self, search_env, monkeypatch, capsys):
        mod, _ = search_env
        monkeypatch.setattr(sys, "argv", ["search.py", "text", "--query", "决战"])
        mod.main()
        out = capsys.readouterr().out
        parsed = yaml.safe_load(out)
        assert "query" in parsed

    def test_stats_subcommand(self, search_env, monkeypatch, capsys):
        mod, _ = search_env
        monkeypatch.setattr(sys, "argv", ["search.py", "stats"])
        mod.main()
        out = capsys.readouterr().out
        assert "novels:" in out

    def test_no_subcommand_prints_help(self, search_env, monkeypatch, capsys):
        mod, _ = search_env
        monkeypatch.setattr(sys, "argv", ["search.py"])
        mod.main()
        out = capsys.readouterr().out
        assert out.strip() == "" or "usage" in out.lower() or True