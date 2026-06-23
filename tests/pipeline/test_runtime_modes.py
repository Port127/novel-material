"""运行模式配置测试。"""

import pytest

from novel_material.pipeline import runtime_modes


def test_standard_mode_defaults_to_first_100_insight_chapters(monkeypatch):
    monkeypatch.setattr(
        runtime_modes,
        "get_settings",
        lambda: {"INSIGHTS_STANDARD_CHAPTER_LIMIT": 100},
    )

    mode = runtime_modes.get_runtime_mode("standard")

    assert mode.name == "standard"
    assert mode.include_core_insights is True
    assert mode.block_on_deep_insights is False
    assert mode.insight_batch_size >= 10
    assert mode.insight_depth == "core"
    assert mode.core_insight_chapter_limit == 100


def test_fast_mode_skips_blocking_insights():
    mode = runtime_modes.get_runtime_mode("fast")
    assert mode.include_core_insights is False
    assert mode.block_on_deep_insights is False
    assert mode.core_insight_chapter_limit == 0


def test_deep_mode_keeps_full_core_insights():
    mode = runtime_modes.get_runtime_mode("deep")
    assert mode.include_core_insights is True
    assert mode.include_deep_insights is True
    assert mode.key_chapter_rate > 0
    assert mode.core_insight_chapter_limit is None


@pytest.mark.parametrize("value", [0, -1, "100", True])
def test_standard_mode_rejects_invalid_chapter_limit(monkeypatch, value):
    monkeypatch.setattr(
        runtime_modes,
        "get_settings",
        lambda: {"INSIGHTS_STANDARD_CHAPTER_LIMIT": value},
    )

    with pytest.raises(ValueError, match="INSIGHTS_STANDARD_CHAPTER_LIMIT"):
        runtime_modes.get_runtime_mode("standard")


def test_standard_mode_uses_safe_fallback_when_setting_is_missing(monkeypatch):
    monkeypatch.setattr(runtime_modes, "get_settings", lambda: {})

    assert runtime_modes.get_runtime_mode("standard").core_insight_chapter_limit == 100
