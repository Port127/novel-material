"""
API edge-case tests for backend routers.

Covers gaps NOT in test_api.py:
  - Pipeline conflict (409 when already running)
  - Pipeline trigger with LLM-dependent stages but no LLM config
  - Pipeline trigger with nonexistent material
  - Upload with .md and .epub extensions
  - LLM test endpoint (/api/llm/test)
  - LLM proxy endpoint (/api/llm/proxy)
  - Scene pagination edge cases (page=1 limit=1, large page)
  - Search with limit boundary values
  - Stats endpoint HTML content type
  - Dashboard stats field completeness
  - Tag usage endpoint
  - Multiple sequential tag operations
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_MATERIAL_ID = "nm_novel_20260101_test"


# ── Pipeline Conflict (409) ──────────────────────────────────────────


class TestPipelineConflict:
    def test_trigger_while_running_returns_409(self, client, patched_ps):
        ps = patched_ps
        ps._set_status(TEST_MATERIAL_ID, {"running": True, "current_stage": "analyze"})
        resp = client.post(f"/api/pipeline/{TEST_MATERIAL_ID}/trigger?stage=ingest")
        assert resp.status_code == 409


# ── Pipeline LLM Dependency ──────────────────────────────────────────


class TestPipelineLLMDependency:
    @pytest.mark.parametrize("stage", ["analyze", "finalize"])
    def test_llm_stages_require_config(self, client, patched_ps, stage):
        resp = client.post(f"/api/pipeline/{TEST_MATERIAL_ID}/trigger?stage={stage}")
        assert resp.status_code == 400
        assert "LLM" in resp.json()["detail"]

    @pytest.mark.parametrize("stage", ["analyze", "finalize"])
    def test_llm_stages_with_config(self, client, patched_ps, stage):
        ps = patched_ps
        ps.save_llm_config({"base_url": "http://test.com", "api_key": "key123"})
        resp = client.post(f"/api/pipeline/{TEST_MATERIAL_ID}/trigger?stage={stage}")
        assert resp.status_code == 200


# ── Pipeline nonexistent material ────────────────────────────────────


class TestPipelineNotFound:
    def test_trigger_not_found(self, client):
        resp = client.post("/api/pipeline/nonexistent_id/trigger?stage=ingest")
        assert resp.status_code == 404

    def test_reset_not_found(self, client):
        resp = client.post("/api/pipeline/nonexistent_id/reset")
        assert resp.status_code == 404


# ── Upload edge cases ────────────────────────────────────────────────


class TestUploadEdge:
    def test_upload_md_file(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.md", b"# Title\nContent", "text/markdown")},
            data={"name": "MD Novel", "author": "Author"},
        )
        assert resp.status_code == 200
        assert "material_id" in resp.json()

    def test_upload_epub_file(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.epub", b"fake epub content", "application/epub+zip")},
        )
        assert resp.status_code == 200

    def test_upload_pdf_rejected(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("test.pdf", b"pdf content", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_upload_default_name(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("my_novel.txt", b"content", "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "my_novel"

    def test_upload_default_author(self, client):
        resp = client.post(
            "/api/upload",
            files={"file": ("book.txt", b"content", "text/plain")},
        )
        assert resp.status_code == 200


# ── LLM Test Endpoint ────────────────────────────────────────────────


class TestLLMTestEndpoint:
    def test_no_config_returns_400(self, client):
        resp = client.post("/api/llm/test", json={})
        assert resp.status_code == 400

    def test_with_config_in_body(self, client, patched_ps):
        import httpx
        with patch.object(httpx, "AsyncClient") as mock:
            mock_instance = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_instance.get = AsyncMock(return_value=mock_resp)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock.return_value = mock_instance

            resp = client.post("/api/llm/test", json={
                "base_url": "http://fake.com/v1",
                "api_key": "test_key",
            })
            assert resp.status_code == 200
            assert resp.json()["ok"] is True


# ── LLM Proxy Endpoint ───────────────────────────────────────────────


class TestLLMProxyEndpoint:
    def test_no_config_returns_400(self, client):
        resp = client.post("/api/llm/proxy", json={"messages": []})
        assert resp.status_code == 400

    def test_with_config_proxies(self, client, patched_ps):
        ps = patched_ps
        ps.save_llm_config({"base_url": "http://fake.com/v1", "api_key": "key"})

        import httpx
        with patch.object(httpx, "AsyncClient") as mock:
            mock_instance = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"choices": [{"message": {"content": "hi"}}]}
            mock_instance.post = AsyncMock(return_value=mock_resp)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock.return_value = mock_instance

            resp = client.post("/api/llm/proxy", json={
                "messages": [{"role": "user", "content": "test"}],
            })
            assert resp.status_code == 200


# ── Scene Pagination Edge Cases ──────────────────────────────────────


class TestScenePagination:
    def test_page_1_limit_1(self, client):
        resp = client.get(f"/api/materials/{TEST_MATERIAL_ID}/scenes?page=1&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["scenes"]) <= 1
        assert data["page"] == 1

    def test_large_page_returns_empty(self, client):
        resp = client.get(f"/api/materials/{TEST_MATERIAL_ID}/scenes?page=9999")
        assert resp.status_code == 200
        assert resp.json()["scenes"] == []

    def test_invalid_page_rejected(self, client):
        resp = client.get(f"/api/materials/{TEST_MATERIAL_ID}/scenes?page=0")
        assert resp.status_code == 422

    def test_limit_too_large_rejected(self, client):
        resp = client.get(f"/api/materials/{TEST_MATERIAL_ID}/scenes?limit=999")
        assert resp.status_code == 422


# ── Search Limit Boundaries ──────────────────────────────────────────


class TestSearchLimits:
    def test_search_scenes_limit_1(self, client):
        resp = client.get("/api/search/scenes?scene_type=对决&limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["results"]) <= 1

    def test_search_scenes_limit_100(self, client):
        resp = client.get("/api/search/scenes?scene_type=对决&limit=100")
        assert resp.status_code == 200

    def test_search_scenes_limit_over_max_rejected(self, client):
        resp = client.get("/api/search/scenes?scene_type=对决&limit=101")
        assert resp.status_code == 422

    def test_search_characters_limit_boundary(self, client):
        resp = client.get("/api/search/characters?name=张&limit=100")
        assert resp.status_code == 200

    def test_search_text_min_length(self, client):
        resp = client.get("/api/search/text?query=")
        assert resp.status_code == 422


# ── Stats HTML Content Type ──────────────────────────────────────────


class TestStatsHTML:
    def test_returns_html_content_type(self, client):
        resp = client.get(f"/api/materials/{TEST_MATERIAL_ID}/stats/html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ── Dashboard Stats Completeness ─────────────────────────────────────


class TestDashboardStatsCompleteness:
    def test_all_fields_present(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("novels", "scenes", "characters", "tag_records",
                     "per_novel", "top_scene_types", "top_emotions",
                     "tension_distribution", "top_techniques"):
            assert key in data, f"Missing field: {key}"

    def test_per_novel_structure(self, client):
        resp = client.get("/api/stats")
        data = resp.json()
        for item in data["per_novel"]:
            assert "material_id" in item
            assert "name" in item
            assert "scenes" in item


# ── Tag Operations Sequence ──────────────────────────────────────────


class TestTagOperationsSequence:
    def test_add_then_merge(self, client):
        resp = client.post("/api/tags/add", json={
            "dimension": "scene_type", "value": "临时类型",
        })
        assert resp.status_code == 200

        resp = client.get("/api/tags")
        tags = resp.json()
        assert "临时类型" in tags["scene_type"]["values"]

        resp = client.post("/api/tags/merge", json={
            "dimension": "scene_type", "source": "临时类型", "target": "对决",
        })
        assert resp.status_code == 200

        resp = client.get("/api/tags")
        tags = resp.json()
        assert "临时类型" not in tags["scene_type"]["values"]

    def test_tag_usage_endpoint(self, client):
        resp = client.get("/api/tags/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


# ── Material Endpoints Edge Cases ────────────────────────────────────


class TestMaterialEndpointsEdge:
    def test_get_nonexistent_worldbuilding(self, client):
        resp = client.get("/api/materials/nonexistent/worldbuilding")
        assert resp.status_code == 404

    def test_get_nonexistent_characters(self, client):
        resp = client.get("/api/materials/nonexistent/characters")
        assert resp.status_code == 404

    def test_get_nonexistent_tags(self, client):
        resp = client.get("/api/materials/nonexistent/tags")
        assert resp.status_code == 404

    def test_get_nonexistent_stats(self, client):
        resp = client.get("/api/materials/nonexistent/stats")
        assert resp.status_code == 404

    def test_get_nonexistent_stats_html(self, client):
        resp = client.get("/api/materials/nonexistent/stats/html")
        assert resp.status_code == 404

    def test_scene_detail_not_found(self, client):
        resp = client.get(f"/api/materials/{TEST_MATERIAL_ID}/scenes/nonexistent_scene")
        assert resp.status_code == 404


# ── LLM Settings ─────────────────────────────────────────────────────


class TestLLMSettingsEdge:
    def test_put_then_get(self, client):
        client.put("/api/settings/llm", json={
            "base_url": "http://example.com/v1",
            "api_key": "sk-test123",
            "model": "gpt-4",
        })
        resp = client.get("/api/settings/llm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["base_url"] == "http://example.com/v1"
        assert "api_key" not in data
        assert data["api_key_set"] is True
        assert data["model"] == "gpt-4"

    def test_partial_update_preserves(self, client):
        client.put("/api/settings/llm", json={
            "base_url": "http://a.com", "api_key": "k",
        })
        client.put("/api/settings/llm", json={"model": "gpt-4o"})
        resp = client.get("/api/settings/llm")
        data = resp.json()
        assert data["base_url"] == "http://a.com"
        assert data["model"] == "gpt-4o"
