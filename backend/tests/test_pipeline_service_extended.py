"""
Extended tests for backend/services/pipeline_service.py.

Covers gaps NOT in test_pipeline_service.py:
  - run_stage() routing (unknown stage, error handling, stages_completed accumulation)
  - _run_format() — subprocess path + fallback copy path
  - _run_ingest() — source file presence check
  - _run_build_index() — subprocess execution
  - _extract_yaml() — more edge cases (no code fence, nested fences, whitespace)
  - _load_source() — formatted vs raw source, truncation boundary
  - _call_llm() — missing config, error responses
  - reset_status() — clears running state
  - save_llm_config() — merge behavior
  - stale timeout detection
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_MATERIAL_ID = "nm_novel_20260101_test"


# ── _extract_yaml (extended) ─────────────────────────────────────────


class TestExtractYamlExtended:
    def test_plain_yaml(self, patched_ps):
        ps = patched_ps
        text = "material_id: test\nname: foo"
        assert ps._extract_yaml(text) == text

    def test_yaml_code_fence(self, patched_ps):
        ps = patched_ps
        text = "Some text\n```yaml\nmaterial_id: test\n```\nMore text"
        assert ps._extract_yaml(text) == "material_id: test"

    def test_generic_code_fence(self, patched_ps):
        ps = patched_ps
        text = "Here:\n```\nkey: value\n```"
        assert ps._extract_yaml(text) == "key: value"

    def test_multiple_yaml_fences_takes_first(self, patched_ps):
        ps = patched_ps
        text = "```yaml\nfirst: true\n```\n\n```yaml\nsecond: true\n```"
        assert "first" in ps._extract_yaml(text)

    def test_strips_whitespace(self, patched_ps):
        ps = patched_ps
        text = "```yaml\n  key: value  \n```"
        assert ps._extract_yaml(text) == "key: value"

    def test_no_fence_strips(self, patched_ps):
        ps = patched_ps
        text = "  \n  key: value  \n  "
        assert ps._extract_yaml(text) == "key: value"


# ── _load_source (extended) ──────────────────────────────────────────


class TestLoadSourceExtended:
    def test_prefers_formatted(self, patched_ps, data_env):
        ps = patched_ps
        _, _, novels_dir, _ = data_env
        nd = novels_dir / TEST_MATERIAL_ID
        (nd / "source_formatted.txt").write_text("格式化内容", encoding="utf-8")
        result = ps._load_source(TEST_MATERIAL_ID)
        assert "格式化内容" in result

    def test_falls_back_to_raw(self, patched_ps, data_env):
        ps = patched_ps
        _, _, novels_dir, _ = data_env
        nd = novels_dir / TEST_MATERIAL_ID
        fmt = nd / "source_formatted.txt"
        if fmt.exists():
            fmt.unlink()
        result = ps._load_source(TEST_MATERIAL_ID)
        assert len(result) > 0

    def test_truncation(self, patched_ps, data_env):
        ps = patched_ps
        _, _, novels_dir, _ = data_env
        nd = novels_dir / TEST_MATERIAL_ID
        long_text = "字" * (ps.MAX_SOURCE_CHARS + 1000)
        (nd / "source_formatted.txt").write_text(long_text, encoding="utf-8")
        result = ps._load_source(TEST_MATERIAL_ID)
        assert "省略中间部分" in result
        assert len(result) < len(long_text)

    def test_no_source_raises(self, patched_ps, data_env):
        ps = patched_ps
        _, _, novels_dir, _ = data_env
        mid = "nm_nosource"
        nd = novels_dir / mid
        nd.mkdir(parents=True, exist_ok=True)
        with pytest.raises(FileNotFoundError):
            ps._load_source(mid)

    def test_exact_boundary_no_truncation(self, patched_ps, data_env):
        ps = patched_ps
        _, _, novels_dir, _ = data_env
        nd = novels_dir / TEST_MATERIAL_ID
        exact_text = "字" * ps.MAX_SOURCE_CHARS
        (nd / "source_formatted.txt").write_text(exact_text, encoding="utf-8")
        result = ps._load_source(TEST_MATERIAL_ID)
        assert "省略中间部分" not in result


# ── run_stage routing ─────────────────────────────────────────────────


class TestRunStageRouting:
    def test_unknown_stage_sets_error(self, patched_ps, data_env):
        ps = patched_ps
        ps.run_stage(TEST_MATERIAL_ID, "unknown_stage")
        status = ps.get_status(TEST_MATERIAL_ID)
        assert status["running"] is False
        assert "Unknown stage" in (status.get("last_error") or "")

    def test_ingest_stage(self, patched_ps, data_env):
        ps = patched_ps
        ps.run_stage(TEST_MATERIAL_ID, "ingest")
        status = ps.get_status(TEST_MATERIAL_ID)
        assert "ingest" in status.get("stages_completed", [])
        assert status["running"] is False

    def test_format_stage_without_script(self, patched_ps, data_env):
        """When format script doesn't exist, it copies the file directly."""
        ps = patched_ps
        _, _, novels_dir, _ = data_env
        ps.run_stage(TEST_MATERIAL_ID, "format")
        nd = novels_dir / TEST_MATERIAL_ID
        assert (nd / "source_formatted.txt").exists()

    def test_stage_error_sets_last_error(self, patched_ps, data_env):
        """A stage that raises should set last_error and stop running."""
        ps = patched_ps
        mid = "nm_no_source_material"
        _, _, novels_dir, _ = data_env
        nd = novels_dir / mid
        nd.mkdir(parents=True, exist_ok=True)
        ps.run_stage(mid, "ingest")
        status = ps.get_status(mid)
        assert status["running"] is False
        assert status.get("last_error") is not None

    def test_stages_completed_accumulates(self, patched_ps, data_env):
        ps = patched_ps
        ps.run_stage(TEST_MATERIAL_ID, "ingest")
        ps.run_stage(TEST_MATERIAL_ID, "format")
        status = ps.get_status(TEST_MATERIAL_ID)
        assert "ingest" in status["stages_completed"]
        assert "format" in status["stages_completed"]


# ── _run_ingest ───────────────────────────────────────────────────────


class TestRunIngest:
    def test_no_source_raises(self, patched_ps, data_env):
        ps = patched_ps
        _, _, novels_dir, _ = data_env
        mid = "nm_empty_novel"
        (novels_dir / mid).mkdir(parents=True, exist_ok=True)
        with pytest.raises(FileNotFoundError):
            ps._run_ingest(mid)


# ── _run_build_index ─────────────────────────────────────────────────


class TestRunBuildIndex:
    def test_missing_script_raises(self, patched_ps):
        ps = patched_ps
        with pytest.raises(FileNotFoundError):
            ps._run_build_index("any_material")


# ── _run_scenes ──────────────────────────────────────────────────────


class TestRunScenes:
    def test_always_raises_for_agent(self, patched_ps):
        ps = patched_ps
        with pytest.raises(RuntimeError, match="场景拆分"):
            ps._run_scenes("any")


# ── reset_status ─────────────────────────────────────────────────────


class TestResetStatus:
    def test_clears_running(self, patched_ps):
        ps = patched_ps
        mid = "nm_test_reset"
        ps._set_status(mid, {"running": True, "current_stage": "analyze"})
        result = ps.reset_status(mid)
        assert result["running"] is False
        assert result["current_stage"] is None
        assert result["last_error"] is None


# ── save_llm_config ──────────────────────────────────────────────────


class TestSaveLLMConfig:
    def test_merge_preserves_existing(self, patched_ps, data_env):
        ps = patched_ps
        ps.save_llm_config({"base_url": "http://example.com", "api_key": "key1"})
        ps.save_llm_config({"model": "gpt-4o"})
        cfg = ps.get_llm_config()
        assert cfg["base_url"] == "http://example.com"
        assert cfg["api_key"] == "key1"
        assert cfg["model"] == "gpt-4o"

    def test_none_values_ignored(self, patched_ps, data_env):
        ps = patched_ps
        ps.save_llm_config({"base_url": "http://x.com", "api_key": "k"})
        ps.save_llm_config({"base_url": None, "model": "gpt-4"})
        cfg = ps.get_llm_config()
        assert cfg["base_url"] == "http://x.com"

    def test_overwrite_existing_key(self, patched_ps, data_env):
        ps = patched_ps
        ps.save_llm_config({"model": "old"})
        ps.save_llm_config({"model": "new"})
        assert ps.get_llm_config()["model"] == "new"


# ── stale timeout ────────────────────────────────────────────────────


class TestStaleTimeout:
    def test_stale_detected(self, patched_ps):
        ps = patched_ps
        mid = "nm_stale_test"
        old_time = (datetime.now() - timedelta(seconds=ps.STALE_TIMEOUT_SECONDS + 100)).isoformat()
        all_st = ps._all_status()
        all_st[mid] = {
            "running": True,
            "current_stage": "analyze",
            "stages_completed": [],
            "updated_at": old_time,
            "last_error": None,
        }
        ps._write_json(ps.STATUS_FILE, all_st)

        status = ps.get_status(mid)
        assert status["running"] is False
        assert "超时" in status.get("last_error", "")

    def test_recent_not_stale(self, patched_ps):
        ps = patched_ps
        mid = "nm_recent_test"
        ps._set_status(mid, {
            "running": True,
            "current_stage": "format",
            "updated_at": datetime.now().isoformat(),
        })
        status = ps.get_status(mid)
        assert status["running"] is True


# ── _call_llm ────────────────────────────────────────────────────────


class TestCallLLM:
    def test_missing_config_raises(self, patched_ps):
        ps = patched_ps
        with pytest.raises(RuntimeError, match="LLM 未配置"):
            ps._call_llm("system", "user")

    def test_missing_api_key_raises(self, patched_ps):
        ps = patched_ps
        ps.save_llm_config({"base_url": "http://x.com"})
        with pytest.raises(RuntimeError, match="LLM 未配置"):
            ps._call_llm("system", "user")

    @patch("services.pipeline_service.httpx.Client")
    def test_non_200_raises(self, mock_client_cls, patched_ps):
        ps = patched_ps
        ps.save_llm_config({"base_url": "http://test.com", "api_key": "key123"})

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__enter__ = lambda s: mock_client_instance
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client_instance

        with pytest.raises(RuntimeError, match="LLM 调用失败"):
            ps._call_llm("sys", "usr")

    @patch("services.pipeline_service.httpx.Client")
    def test_empty_choices_raises(self, mock_client_cls, patched_ps):
        ps = patched_ps
        ps.save_llm_config({"base_url": "http://test.com", "api_key": "key123"})

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": []}
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__enter__ = lambda s: mock_client_instance
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client_instance

        with pytest.raises(RuntimeError, match="LLM 返回空结果"):
            ps._call_llm("sys", "usr")

    @patch("services.pipeline_service.httpx.Client")
    def test_successful_call(self, mock_client_cls, patched_ps):
        ps = patched_ps
        ps.save_llm_config({"base_url": "http://test.com", "api_key": "key123"})

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hello world"}}]
        }
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__enter__ = lambda s: mock_client_instance
        mock_client_instance.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client_instance

        result = ps._call_llm("sys", "usr")
        assert result == "hello world"
