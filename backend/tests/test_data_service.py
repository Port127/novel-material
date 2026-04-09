"""Unit tests for data_service."""

from tests.conftest import TEST_MATERIAL_ID

MID = TEST_MATERIAL_ID


def test_list_materials(patched_ds):
    result = patched_ds.list_materials()
    assert len(result) >= 1
    assert result[0]["id"] == MID
    assert result[0]["scene_count"] == 3


def test_get_material(patched_ds):
    m = patched_ds.get_material(MID)
    assert m is not None
    assert m["material_id"] == MID
    assert m["has_outline"] is True
    assert m["has_worldbuilding"] is True
    assert m["has_characters"] is True
    assert m["has_tags"] is True
    assert m["has_stats"] is True
    assert m["has_scenes"] is True
    assert m["scene_count"] == 3
    assert m["character_count"] == 2


def test_get_material_not_found(patched_ds):
    assert patched_ds.get_material("nonexistent") is None


def test_get_outline(patched_ds):
    o = patched_ds.get_outline(MID)
    assert o is not None
    assert o["material_id"] == MID
    assert "premise" in o


def test_get_worldbuilding(patched_ds):
    w = patched_ds.get_worldbuilding(MID)
    assert w is not None
    assert "power_system" in w


def test_get_characters_yaml(patched_ds):
    c = patched_ds.get_characters_yaml(MID)
    assert c is not None
    assert len(c["roster"]) == 2


def test_get_novel_tags(patched_ds):
    t = patched_ds.get_novel_tags(MID)
    assert t is not None
    assert t["material_id"] == MID


def test_get_stats(patched_ds):
    s = patched_ds.get_stats(MID)
    assert s is not None
    assert s["total_scenes"] == 3


def test_get_stats_html(patched_ds):
    html = patched_ds.get_stats_html(MID)
    assert html is not None
    assert "Stats" in html


def test_get_stats_html_missing(patched_ds):
    assert patched_ds.get_stats_html("nonexistent") is None


# ── Scenes ─────────────────────────────────────────────────────

def test_get_scenes_default(patched_ds):
    result = patched_ds.get_scenes(MID)
    assert result["total"] == 3
    assert result["page"] == 1
    assert len(result["scenes"]) == 3
    scene = result["scenes"][0]
    assert "tags" in scene
    assert "characters" in scene


def test_get_scenes_pagination(patched_ds):
    result = patched_ds.get_scenes(MID, page=1, limit=2)
    assert len(result["scenes"]) == 2
    result2 = patched_ds.get_scenes(MID, page=2, limit=2)
    assert len(result2["scenes"]) == 1


def test_get_scene_detail_from_yaml(patched_ds):
    scene = patched_ds.get_scene_detail(MID, f"{MID}_ch001_s1")
    assert scene is not None


def test_get_scene_detail_not_found(patched_ds):
    assert patched_ds.get_scene_detail(MID, "nonexistent_scene") is None


# ── Search ─────────────────────────────────────────────────────

def test_search_scenes_single_tag(patched_ds):
    result = patched_ds.search_scenes({"scene_type": "对决", "limit": 10})
    assert result["total"] >= 1


def test_search_scenes_character(patched_ds):
    result = patched_ds.search_scenes({"character": "张三", "limit": 10})
    assert result["total"] >= 1


def test_search_scenes_material_filter(patched_ds):
    result = patched_ds.search_scenes({"material": MID, "limit": 50})
    assert result["total"] == 3


def test_search_scenes_no_match(patched_ds):
    result = patched_ds.search_scenes({"scene_type": "不存在的类型", "limit": 10})
    assert result["total"] == 0


def test_search_scenes_tension_filter(patched_ds):
    result = patched_ds.search_scenes({"material": MID, "tension_min": 4, "limit": 10})
    for s in result["results"]:
        assert s["tension"] >= 4


def test_search_characters(patched_ds):
    result = patched_ds.search_characters({"name": "张", "limit": 10})
    assert result["total"] >= 1
    assert result["results"][0]["name"] == "张三"


def test_search_characters_by_role(patched_ds):
    result = patched_ds.search_characters({"role": "antagonist", "limit": 10})
    assert result["total"] >= 1
    assert result["results"][0]["name"] == "李四"


def test_search_text(patched_ds):
    result = patched_ds.search_text("黎明", limit=10)
    assert result["total"] >= 1


def test_search_text_empty(patched_ds):
    result = patched_ds.search_text("完全不存在", limit=10)
    assert result["total"] == 0


# ── Dashboard ──────────────────────────────────────────────────

def test_dashboard_stats(patched_ds):
    s = patched_ds.get_dashboard_stats()
    assert s["novels"] >= 1
    assert s["scenes"] >= 1
    assert s["characters"] >= 1
    assert s["tag_records"] >= 1
    assert len(s["per_novel"]) >= 1
    assert "top_scene_types" in s
    assert "tension_distribution" in s


# ── Tag Management ─────────────────────────────────────────────

def test_get_tag_dict(patched_ds):
    tags = patched_ds.get_tag_dict()
    assert "scene_type" in tags
    assert "对决" in tags["scene_type"]["values"]


def test_add_tag_value(patched_ds):
    result = patched_ds.add_tag_value("scene_type", "新场景类型")
    assert result["ok"] is True

    tags = patched_ds.get_tag_dict()
    assert "新场景类型" in tags["scene_type"]["values"]


def test_add_tag_value_duplicate(patched_ds):
    result = patched_ds.add_tag_value("scene_type", "对决")
    assert result["ok"] is False


def test_add_tag_value_unknown_dim(patched_ds):
    result = patched_ds.add_tag_value("unknown_dim", "val")
    assert result["ok"] is False


def test_merge_tag_values(patched_ds):
    patched_ds.add_tag_value("emotion", "热血")
    result = patched_ds.merge_tag_values("emotion", "热血", "燃")
    assert result["ok"] is True
    assert result["merged"] == "热血"
    assert result["into"] == "燃"

    tags = patched_ds.get_tag_dict()
    assert "热血" not in tags["emotion"]["values"]


def test_merge_tag_target_missing(patched_ds):
    result = patched_ds.merge_tag_values("emotion", "燃", "不存在的目标")
    assert result["ok"] is False


def test_get_tag_usage(patched_ds):
    usage = patched_ds.get_tag_usage()
    assert "scene_type" in usage


# ── Register ───────────────────────────────────────────────────

def test_register_material(patched_ds):
    patched_ds.register_material("nm_novel_20260102_new", "新小说", "新作者")
    materials = patched_ds.list_materials()
    ids = [m["id"] for m in materials]
    assert "nm_novel_20260102_new" in ids


def test_register_material_idempotent(patched_ds):
    patched_ds.register_material(MID, "重复", "重复")
    materials = patched_ds.list_materials()
    count = sum(1 for m in materials if m["id"] == MID)
    assert count == 1
