"""题材感知 profile 加载测试。"""

from novel_material.analysis_profiles import load_profile, load_profiles, merge_profiles


def test_load_common_profile():
    profile = load_profile("common")
    assert profile.name == "common"
    assert "core_event" in profile.required_fields
    assert "field_presence" in profile.quality_rules


def test_load_profiles_preserves_order():
    profiles = load_profiles(["common", "xuanhuan"])
    assert [p.name for p in profiles] == ["common", "xuanhuan"]


def test_merge_profiles_combines_fields_and_prompt_additions():
    merged = merge_profiles(load_profiles(["common", "xuanhuan"]))
    assert merged.name == "common+xuanhuan"
    assert "core_event" in merged.required_fields
    assert "power_progression" in merged.required_fields
    assert any("能力成长" in item for item in merged.prompt_additions)
