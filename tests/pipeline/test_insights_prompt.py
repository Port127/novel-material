"""深度分析 prompt 构造测试。"""

from novel_material.analysis_profiles import load_profiles, merge_profiles
from novel_material.pipeline.insights_prompt import (
    build_insight_schema_text,
    build_insight_system_prompt,
    build_repair_prompt,
)


def test_schema_includes_common_and_genre_fields():
    profile = merge_profiles(load_profiles(["common", "xuanhuan"]))
    schema = build_insight_schema_text(profile)
    assert '"core_event"' in schema
    assert '"power_progression"' in schema


def test_system_prompt_includes_profile_guidance():
    profile = merge_profiles(load_profiles(["common", "suspense"]))
    prompt = build_insight_system_prompt(profile)
    assert "线索" in prompt
    assert "可复用写法" in prompt
    assert "只输出 JSON" in prompt
    assert "不要编造" in prompt


def test_repair_prompt_includes_validation_errors():
    prompt = build_repair_prompt(["缺少必填字段: core_event"], {"common": {}})
    assert "缺少必填字段: core_event" in prompt
    assert "只修复这些错误" in prompt
