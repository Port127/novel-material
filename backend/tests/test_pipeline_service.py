"""Unit tests for pipeline_service."""

import json
from tests.conftest import TEST_MATERIAL_ID

MID = TEST_MATERIAL_ID


def test_get_status_default(patched_ps):
    st = patched_ps.get_status(MID)
    assert st["running"] is False
    assert st["stages_completed"] == []
    assert st["current_stage"] is None


def test_set_and_get_status(patched_ps):
    patched_ps._set_status(MID, {"running": True, "current_stage": "analyze"})
    st = patched_ps.get_status(MID)
    assert st["running"] is True
    assert st["current_stage"] == "analyze"
    assert st["updated_at"] is not None


def test_reset_status(patched_ps):
    patched_ps._set_status(MID, {"running": True, "current_stage": "analyze"})
    result = patched_ps.reset_status(MID)
    assert result["running"] is False
    assert result["current_stage"] is None


def test_stale_timeout(patched_ps):
    from datetime import datetime, timedelta

    old_time = (datetime.now() - timedelta(seconds=700)).isoformat()
    all_st = patched_ps._all_status()
    all_st[MID] = {
        "stages_completed": [],
        "running": True,
        "current_stage": "analyze",
        "updated_at": old_time,
    }
    patched_ps._write_json(patched_ps.STATUS_FILE, all_st)

    st = patched_ps.get_status(MID)
    assert st["running"] is False
    assert "超时" in st["last_error"]


def test_get_llm_config_empty(patched_ps):
    cfg = patched_ps.get_llm_config()
    assert isinstance(cfg, dict)


def test_save_llm_config(patched_ps):
    patched_ps.save_llm_config({"base_url": "http://test:8080/v1", "model": "gpt-4"})
    cfg = patched_ps.get_llm_config()
    assert cfg["base_url"] == "http://test:8080/v1"
    assert cfg["model"] == "gpt-4"


def test_save_llm_config_merge(patched_ps):
    patched_ps.save_llm_config({"base_url": "http://a/v1"})
    patched_ps.save_llm_config({"model": "gpt-4o"})
    cfg = patched_ps.get_llm_config()
    assert cfg["base_url"] == "http://a/v1"
    assert cfg["model"] == "gpt-4o"


def test_extract_yaml():
    from services.pipeline_service import _extract_yaml

    raw_fenced = "Here is the output:\n```yaml\nkey: value\n```\nDone."
    assert _extract_yaml(raw_fenced) == "key: value"

    raw_plain = "key: value\nlist:\n  - a"
    assert _extract_yaml(raw_plain) == raw_plain

    raw_generic = "```\nkey: value\n```"
    assert _extract_yaml(raw_generic) == "key: value"


def test_load_source(patched_ps, data_env):
    data_dir, db_path, novels_dir, tmp_path = data_env
    text = patched_ps._load_source(MID)
    assert "第1章" in text


def test_load_source_truncation(patched_ps, data_env):
    data_dir, db_path, novels_dir, tmp_path = data_env
    nd = novels_dir / MID
    big_text = "A" * 100_000
    (nd / "source.txt").write_text(big_text, encoding="utf-8")

    text = patched_ps._load_source(MID)
    assert "省略中间部分" in text
    assert len(text) < 100_000


def test_run_ingest(patched_ps, data_env):
    patched_ps._run_ingest(MID)


def test_run_stage_scenes_requires_agent(patched_ps, data_env):
    patched_ps.run_stage(MID, "scenes")
    st = patched_ps.get_status(MID)
    assert st["running"] is False
    assert "Agent" in st["last_error"]


def test_search_scenes_multi_value(patched_ds):
    """Multi-value comma-separated tags should match any value (OR within dim)."""
    result = patched_ds.search_scenes({"scene_type": "对决,回忆", "limit": 10})
    assert result["total"] >= 2


def test_search_scenes_single_still_works(patched_ds):
    result = patched_ds.search_scenes({"scene_type": "对决", "limit": 10})
    assert result["total"] >= 1
