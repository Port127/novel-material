"""Tests for quality_audit.py."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from quality_audit import compute_batch_quality, detect_quality_drift, load_scenes, _as_list


class TestAsListHelper:
    def test_none(self):
        assert _as_list(None) == []

    def test_string(self):
        assert _as_list("hello") == ["hello"]

    def test_list(self):
        assert _as_list(["a", "b"]) == ["a", "b"]


class TestLoadScenes:
    def test_load_all(self, novel_env):
        _, _, novel_dir, _ = novel_env
        scenes_dir = novel_dir / "scenes"
        scenes = load_scenes(scenes_dir)
        assert len(scenes) == 10

    def test_load_by_range(self, novel_env):
        _, _, novel_dir, _ = novel_env
        scenes_dir = novel_dir / "scenes"
        scenes = load_scenes(scenes_dir, "1-5")
        assert len(scenes) == 5

    def test_load_empty_range(self, novel_env):
        _, _, novel_dir, _ = novel_env
        scenes_dir = novel_dir / "scenes"
        scenes = load_scenes(scenes_dir, "100-200")
        assert len(scenes) == 0


class TestComputeBatchQuality:
    def test_empty(self):
        result = compute_batch_quality([])
        assert result["status"] == "empty"

    def test_valid_batch(self, novel_env):
        _, _, novel_dir, _ = novel_env
        scenes = load_scenes(novel_dir / "scenes", "1-10")
        result = compute_batch_quality(scenes)
        assert result["scenes_count"] == 10
        assert "quality" in result
        q = result["quality"]
        assert 0 <= q["tag_diversity"] <= 1
        assert 0 <= q["empty_field_rate"] <= 1
        assert q["avg_tags_per_scene"] > 0

    def test_parse_error_scenes(self):
        scenes = [{"_file": "ch001.yaml", "_parse_error": True}]
        result = compute_batch_quality(scenes)
        assert result["parse_errors"] == 1


class TestDetectQualityDrift:
    def test_insufficient_batches(self):
        batches = [{"quality": {"tag_diversity": 0.8}} for _ in range(3)]
        result = detect_quality_drift(batches)
        assert result["drift_detected"] is False

    def test_stable_quality(self):
        batches = [
            {"quality": {"tag_diversity": 0.8, "empty_field_rate": 0.1, "avg_tags_per_scene": 15}}
            for _ in range(9)
        ]
        result = detect_quality_drift(batches)
        assert result["drift_detected"] is False

    def test_degraded_quality(self):
        early = [{"quality": {"tag_diversity": 0.9, "empty_field_rate": 0.05, "avg_tags_per_scene": 20}}] * 3
        mid = [{"quality": {"tag_diversity": 0.7, "empty_field_rate": 0.1, "avg_tags_per_scene": 15}}] * 3
        late = [{"quality": {"tag_diversity": 0.2, "empty_field_rate": 0.4, "avg_tags_per_scene": 5}}] * 3
        result = detect_quality_drift(early + mid + late)
        assert result["drift_detected"] is True
        assert len(result["warnings"]) > 0
