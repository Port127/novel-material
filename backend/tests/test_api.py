"""API endpoint tests — covers all routers."""

import io
from tests.conftest import TEST_MATERIAL_ID

MID = TEST_MATERIAL_ID


# ── Health ────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Materials ─────────────────────────────────────────────────

def test_list_materials(client):
    r = client.get("/api/materials")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    m = data[0]
    assert m["id"] == MID
    assert "event_count" in m


def test_get_material(client):
    r = client.get(f"/api/materials/{MID}")
    assert r.status_code == 200
    d = r.json()
    assert d["material_id"] == MID
    assert d["has_outline"] is True
    assert d["has_characters"] is True
    assert d["has_tags"] is True
    assert d["has_stats"] is True
    assert d["has_events"] is True


def test_get_material_not_found(client):
    r = client.get("/api/materials/nonexistent")
    assert r.status_code == 404


def test_get_outline(client):
    r = client.get(f"/api/materials/{MID}/outline")
    assert r.status_code == 200
    assert r.json()["material_id"] == MID


def test_get_outline_not_found(client):
    r = client.get("/api/materials/nonexistent/outline")
    assert r.status_code == 404


def test_get_worldbuilding(client):
    r = client.get(f"/api/materials/{MID}/worldbuilding")
    assert r.status_code == 200
    assert "power_system" in r.json()


def test_get_characters(client):
    r = client.get(f"/api/materials/{MID}/characters")
    assert r.status_code == 200
    assert "roster" in r.json()


def test_get_novel_tags(client):
    r = client.get(f"/api/materials/{MID}/tags")
    assert r.status_code == 200
    assert r.json()["material_id"] == MID


def test_get_events_paginated(client):
    r = client.get(f"/api/materials/{MID}/events?page=1&limit=2")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 3
    assert d["page"] == 1
    assert len(d["events"]) == 2


def test_get_event_detail(client):
    eid = f"{MID}_ch001_s1"
    r = client.get(f"/api/materials/{MID}/events/{eid}")
    assert r.status_code == 200


def test_get_event_not_found(client):
    r = client.get(f"/api/materials/{MID}/events/nonexistent")
    assert r.status_code == 404


def test_get_stats(client):
    r = client.get(f"/api/materials/{MID}/stats")
    assert r.status_code == 200
    assert "total_events" in r.json()


def test_get_stats_html(client):
    r = client.get(f"/api/materials/{MID}/stats/html")
    assert r.status_code == 200
    assert "Stats" in r.text


# ── Search ────────────────────────────────────────────────────

def test_search_events_by_type(client):
    r = client.get("/api/search/events?event_type=对决")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
    for s in d["results"]:
        assert "对决" in s["tags"].get("event_type", [])


def test_search_events_by_emotion(client):
    r = client.get("/api/search/events?emotion=燃")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_search_events_by_character(client):
    r = client.get("/api/search/events?character=张三")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_search_events_by_material(client):
    r = client.get(f"/api/search/events?material={MID}")
    assert r.status_code == 200
    assert r.json()["total"] == 3


def test_search_events_multi_filter(client):
    r = client.get("/api/search/events?event_type=对决&emotion=燃")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_search_events_tension_range(client):
    r = client.get(f"/api/search/events?material={MID}&tension_min=4")
    assert r.status_code == 200
    for s in r.json()["results"]:
        assert s["tension"] >= 4


def test_search_events_relaxation(client):
    r = client.get("/api/search/events?event_type=对决&emotion=温暖&conflict=人与自然")
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d["relaxed"], bool)


def test_search_characters_by_name(client):
    r = client.get("/api/search/characters?name=张三")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
    assert d["results"][0]["name"] == "张三"


def test_search_characters_by_archetype(client):
    r = client.get("/api/search/characters?archetype=暗影")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_search_characters_by_role(client):
    r = client.get("/api/search/characters?role=protagonist")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_search_characters_by_material(client):
    r = client.get(f"/api/search/characters?material={MID}")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_search_text(client):
    r = client.get("/api/search/text?query=黎明")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1


def test_search_text_no_match(client):
    r = client.get("/api/search/text?query=不存在的内容xyz")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_dashboard_stats(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    d = r.json()
    assert d["novels"] >= 1
    assert d["events"] >= 1
    assert d["characters"] >= 1
    assert "per_novel" in d
    assert "top_event_types" in d
    assert "tension_distribution" in d


# ── Tags ──────────────────────────────────────────────────────

def test_get_tag_dict(client):
    r = client.get("/api/tags")
    assert r.status_code == 200
    d = r.json()
    assert "event_type" in d
    assert "对决" in d["event_type"]["values"]


def test_get_tag_usage(client):
    r = client.get("/api/tags/usage")
    assert r.status_code == 200
    d = r.json()
    assert "event_type" in d


def test_add_tag(client):
    r = client.post("/api/tags/add", json={"dimension": "event_type", "value": "新标签"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r2 = client.get("/api/tags")
    assert "新标签" in r2.json()["event_type"]["values"]


def test_add_tag_duplicate(client):
    r = client.post("/api/tags/add", json={"dimension": "event_type", "value": "对决"})
    assert r.status_code == 400


def test_add_tag_unknown_dimension(client):
    r = client.post("/api/tags/add", json={"dimension": "fake_dim", "value": "x"})
    assert r.status_code == 400


def test_merge_tags(client):
    client.post("/api/tags/add", json={"dimension": "emotion", "value": "热血"})
    r = client.post("/api/tags/merge", json={
        "dimension": "emotion", "source": "热血", "target": "燃",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r2 = client.get("/api/tags")
    assert "热血" not in r2.json()["emotion"]["values"]


def test_merge_tags_target_not_found(client):
    r = client.post("/api/tags/merge", json={
        "dimension": "emotion", "source": "燃", "target": "不存在",
    })
    assert r.status_code == 400


# ── Pipeline ──────────────────────────────────────────────────

def test_pipeline_status(client):
    r = client.get(f"/api/pipeline/{MID}/status")
    assert r.status_code == 200
    d = r.json()
    assert "running" in d
    assert "stages_completed" in d


def test_pipeline_trigger_invalid_stage(client):
    r = client.post(f"/api/pipeline/{MID}/trigger?stage=invalid_stage")
    assert r.status_code == 400


def test_pipeline_trigger_not_found(client):
    r = client.post("/api/pipeline/nonexistent/trigger?stage=ingest")
    assert r.status_code == 404


def test_pipeline_reset(client):
    r = client.post(f"/api/pipeline/{MID}/reset")
    assert r.status_code == 200
    assert r.json()["message"] == "已重置"


def test_pipeline_reset_not_found(client):
    r = client.post("/api/pipeline/nonexistent/reset")
    assert r.status_code == 404


# ── LLM Settings ──────────────────────────────────────────────

def test_get_llm_settings(client):
    r = client.get("/api/settings/llm")
    assert r.status_code == 200


def test_save_llm_settings(client):
    r = client.put("/api/settings/llm", json={
        "base_url": "http://localhost:8080/v1",
        "model": "test-model",
    })
    assert r.status_code == 200

    r2 = client.get("/api/settings/llm")
    d = r2.json()
    assert d["base_url"] == "http://localhost:8080/v1"
    assert d["model"] == "test-model"


def test_llm_settings_hide_api_key(client):
    client.put("/api/settings/llm", json={
        "base_url": "http://localhost:8080/v1",
        "api_key": "sk-secret123",
    })
    r = client.get("/api/settings/llm")
    d = r.json()
    assert "api_key" not in d
    assert d.get("api_key_set") is True


# ── Upload ────────────────────────────────────────────────────

def test_upload_novel(client):
    content = "第1章 测试\n测试正文内容。\n\n第2章 继续\n更多内容。".encode("utf-8")
    files = {"file": ("test_novel.txt", io.BytesIO(content), "text/plain")}
    r = client.post("/api/upload", files=files, data={"name": "上传测试", "author": "test"})
    assert r.status_code == 200
    d = r.json()
    assert "material_id" in d
    assert d["name"] == "上传测试"


def test_upload_novel_unsupported_type(client):
    files = {"file": ("test.pdf", io.BytesIO(b"fake"), "application/pdf")}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 400


def test_upload_novel_no_file(client):
    r = client.post("/api/upload")
    assert r.status_code == 422
