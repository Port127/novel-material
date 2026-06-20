"""运行模式配置测试。"""

from novel_material.pipeline.runtime_modes import get_runtime_mode


def test_standard_mode_defaults_are_time_bounded():
    mode = get_runtime_mode("standard")
    assert mode.name == "standard"
    assert mode.include_core_insights is True
    assert mode.block_on_deep_insights is False
    assert mode.insight_batch_size >= 10
    assert mode.insight_depth == "core"


def test_fast_mode_skips_blocking_insights():
    mode = get_runtime_mode("fast")
    assert mode.include_core_insights is False
    assert mode.block_on_deep_insights is False


def test_deep_mode_enables_key_chapter_deep_insights():
    mode = get_runtime_mode("deep")
    assert mode.include_core_insights is True
    assert mode.include_deep_insights is True
    assert mode.key_chapter_rate > 0
