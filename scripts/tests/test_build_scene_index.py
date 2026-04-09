"""Tests for build_scene_index.py."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from build_scene_index import build_index, _as_list


class TestAsListHelper:
    def test_none(self):
        assert _as_list(None) == []

    def test_scalar(self):
        assert _as_list("val") == ["val"]

    def test_list(self):
        assert _as_list(["a", "b"]) == ["a", "b"]


class TestBuildIndex:
    def test_builds_outputs(self, novel_env):
        _, _, novel_dir, mid = novel_env
        build_index(mid)

        index_path = novel_dir / "scenes_index.yaml"
        manifest_path = novel_dir / "scenes_manifest.yaml"
        assert index_path.exists()
        assert manifest_path.exists()

        with open(index_path, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f)
        assert index["material_id"] == mid
        assert index["total_scenes"] == 10
        assert "scene_type" in index
        assert "character" in index

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        assert len(manifest["scenes"]) == 10

    def test_updates_meta(self, novel_env):
        _, _, novel_dir, mid = novel_env
        build_index(mid)

        with open(novel_dir / "meta.yaml", "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        assert meta["pipeline"]["index_built"] is True
        assert meta["pipeline"]["manifest_scenes"] == 10
