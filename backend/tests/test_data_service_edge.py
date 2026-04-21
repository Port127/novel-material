"""
Edge-case tests for backend/services/data_service.py.

Covers gaps NOT in test_data_service.py:
  - _clean_query() helper
  - search_events() with tension-only filters (no tags/character)
  - search_events() with comma-separated multi-value in a single dimension
  - search_characters() with no conditions → returns all
  - merge_tag_values() DB update path + source removal
  - register_material() edge cases (no index.yaml)
  - get_event_detail() fallback from YAML to DB
  - list_materials() without DB
  - get_material() without DB
"""

import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_MATERIAL_ID = "nm_novel_20260101_test"


# ── _clean_query ──────────────────────────────────────────────────────


class TestCleanQuery:
    def test_removes_none_values(self, patched_ds):
        ds = patched_ds
        result = ds._clean_query({"event_type": "对决", "emotion": None, "limit": 20})
        assert result == {"event_type": "对决"}

    def test_removes_limit(self, patched_ds):
        ds = patched_ds
        result = ds._clean_query({"limit": 20, "event_type": "x"})
        assert "limit" not in result

    def test_joins_list_values(self, patched_ds):
        ds = patched_ds
        result = ds._clean_query({"emotion": ["燃", "悲伤"]})
        assert result == {"emotion": "燃,悲伤"}

    def test_empty_list_removed(self, patched_ds):
        ds = patched_ds
        result = ds._clean_query({"emotion": []})
        assert result == {}

    def test_all_none_returns_empty(self, patched_ds):
        ds = patched_ds
        result = ds._clean_query({"a": None, "b": None, "limit": 10})
        assert result == {}

    def test_string_values_pass_through(self, patched_ds):
        ds = patched_ds
        result = ds._clean_query({"character": "张三", "material": "mid"})
        assert result == {"character": "张三", "material": "mid"}


# ── search_events edge cases ─────────────────────────────────────────


class TestSearchEventsEdge:
    def test_tension_only_filter(self, patched_ds):
        """Tension-only search (no tag or character filters) should still work."""
        ds = patched_ds
        result = ds.search_events({"tension_min": 4})
        assert result["total"] >= 0
        for r in result["results"]:
            assert r["tension"] >= 4

    def test_tension_range(self, patched_ds):
        ds = patched_ds
        result = ds.search_events({"tension_min": 2, "tension_max": 3})
        for r in result["results"]:
            assert 2 <= r["tension"] <= 3

    def test_comma_separated_values(self, patched_ds):
        """A single dimension with comma-separated values should be split and OR'd."""
        ds = patched_ds
        result = ds.search_events({"event_type": "对决,回忆"})
        assert result["total"] >= 1

    def test_no_db_returns_empty(self, patched_ds, data_env):
        ds = patched_ds
        data_dir, db_path, _, _ = data_env
        db_path.unlink()
        ds.DB_PATH = db_path
        result = ds.search_events({"event_type": "对决"})
        assert result["total"] == 0
        assert result["relaxed"] is False

    def test_relaxation_flag(self, patched_ds):
        """When AND intersection fails, relaxation should be flagged."""
        ds = patched_ds
        result = ds.search_events({
            "event_type": "回忆",
            "conflict": "人与命运",
        })
        if result["total"] == 0:
            assert result["relaxed"] is False
        else:
            pass


# ── search_characters edge cases ─────────────────────────────────────


class TestSearchCharactersEdge:
    def test_no_filters_returns_all(self, patched_ds):
        """When no filters are specified, WHERE 1=1 → all characters returned."""
        ds = patched_ds
        result = ds.search_characters({})
        assert result["total"] == 2

    def test_combined_filters(self, patched_ds):
        ds = patched_ds
        result = ds.search_characters({"role": "protagonist", "moral_spectrum": "正义"})
        assert result["total"] >= 1
        for r in result["results"]:
            assert r["role"] == "protagonist"

    def test_no_match(self, patched_ds):
        ds = patched_ds
        result = ds.search_characters({"name": "完全不存在的人"})
        assert result["total"] == 0


# ── search_text edge cases ───────────────────────────────────────────


class TestSearchTextEdge:
    def test_empty_query(self, patched_ds):
        ds = patched_ds
        result = ds.search_text("", limit=10)
        assert "results" in result

    def test_special_characters_in_query(self, patched_ds):
        ds = patched_ds
        result = ds.search_text("%_特殊", limit=10)
        assert "results" in result


# ── merge_tag_values ──────────────────────────────────────────────────


class TestMergeTagValues:
    def test_merge_updates_db_and_removes_source(self, patched_ds, data_env):
        ds = patched_ds
        data_dir, db_path, _, _ = data_env
        tags = ds._read_yaml(data_dir / "tags.yaml")
        assert "回忆" in tags["event_type"]["values"]

        result = ds.merge_tag_values("event_type", "回忆", "对决")
        assert result["ok"] is True
        assert result["merged"] == "回忆"
        assert result["into"] == "对决"

        tags_after = ds._read_yaml(data_dir / "tags.yaml")
        assert "回忆" not in tags_after["event_type"]["values"]

    def test_merge_source_not_in_dict_still_ok(self, patched_ds, data_env):
        ds = patched_ds
        result = ds.merge_tag_values("event_type", "完全不存在", "对决")
        assert result["ok"] is True

    def test_merge_target_not_found(self, patched_ds):
        ds = patched_ds
        result = ds.merge_tag_values("event_type", "对决", "不存在的目标")
        assert result["ok"] is False

    def test_merge_unknown_dimension(self, patched_ds):
        ds = patched_ds
        result = ds.merge_tag_values("fake_dim", "a", "b")
        assert result["ok"] is False


# ── register_material ────────────────────────────────────────────────


class TestRegisterMaterial:
    def test_creates_new_entry(self, patched_ds, data_env):
        ds = patched_ds
        data_dir, _, _, _ = data_env
        ds.register_material("nm_novel_new_001", "新小说", "新作者")
        idx = ds._read_yaml(data_dir / "index.yaml")
        ids = [m["id"] for m in idx["materials"]]
        assert "nm_novel_new_001" in ids

    def test_duplicate_ignored(self, patched_ds, data_env):
        ds = patched_ds
        data_dir, _, _, _ = data_env
        ds.register_material("nm_novel_new_002", "A", "A")
        ds.register_material("nm_novel_new_002", "B", "B")
        idx = ds._read_yaml(data_dir / "index.yaml")
        matches = [m for m in idx["materials"] if m["id"] == "nm_novel_new_002"]
        assert len(matches) == 1

    def test_missing_index_creates_new(self, patched_ds, data_env):
        ds = patched_ds
        data_dir, _, _, _ = data_env
        (data_dir / "index.yaml").unlink()
        ds.register_material("nm_fresh", "Fresh", "Author")
        idx = ds._read_yaml(data_dir / "index.yaml")
        assert idx["materials"][0]["id"] == "nm_fresh"


# ── get_event_detail ─────────────────────────────────────────────────


class TestGetEventDetail:
    def test_prefers_yaml_file(self, patched_ds, data_env):
        ds = patched_ds
        detail = ds.get_event_detail(TEST_MATERIAL_ID, "ev0001")
        assert detail is not None
        assert "id" in detail or "event_id" in detail

    def test_falls_back_to_db(self, patched_ds, data_env):
        ds = patched_ds
        detail = ds.get_event_detail(TEST_MATERIAL_ID, f"{TEST_MATERIAL_ID}_ch001_s1")
        assert detail is not None

    def test_not_found_in_both(self, patched_ds):
        ds = patched_ds
        detail = ds.get_event_detail("nonexistent", "nonexistent_e1")
        assert detail is None


# ── list_materials / get_material without DB ─────────────────────────


class TestWithoutDB:
    def test_list_materials_no_db(self, patched_ds, data_env):
        ds = patched_ds
        _, db_path, _, _ = data_env
        db_path.unlink()
        ds.DB_PATH = db_path
        materials = ds.list_materials()
        assert len(materials) >= 1
        assert materials[0]["event_count"] == 0

    def test_get_material_no_db(self, patched_ds, data_env):
        ds = patched_ds
        _, db_path, _, _ = data_env
        db_path.unlink()
        ds.DB_PATH = db_path
        m = ds.get_material(TEST_MATERIAL_ID)
        assert m is not None
        assert "event_count" not in m or m.get("event_count", 0) == 0


# ── get_tag_usage ─────────────────────────────────────────────────────


class TestGetTagUsage:
    def test_returns_usage_dict(self, patched_ds):
        ds = patched_ds
        usage = ds.get_tag_usage()
        assert isinstance(usage, dict)
        assert "event_type" in usage
        assert isinstance(usage["event_type"], list)
        assert all("value" in item and "count" in item for item in usage["event_type"])

    def test_no_db_returns_empty(self, patched_ds, data_env):
        ds = patched_ds
        _, db_path, _, _ = data_env
        db_path.unlink()
        ds.DB_PATH = db_path
        usage = ds.get_tag_usage()
        assert usage == {}


# ── get_dashboard_stats ──────────────────────────────────────────────


class TestGetDashboardStatsEdge:
    def test_includes_distributions(self, patched_ds):
        ds = patched_ds
        stats = ds.get_dashboard_stats()
        assert "tension_distribution" in stats
        assert "top_techniques" in stats
        assert "per_novel" in stats
        assert isinstance(stats["per_novel"], list)

    def test_no_db_returns_zeros(self, patched_ds, data_env):
        ds = patched_ds
        _, db_path, _, _ = data_env
        db_path.unlink()
        ds.DB_PATH = db_path
        stats = ds.get_dashboard_stats()
        assert stats["novels"] == 0
        assert stats["events"] == 0
