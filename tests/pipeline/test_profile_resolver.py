"""根据题材元数据选择 analysis profiles。"""

from novel_material.pipeline.profile_resolver import resolve_profile_names


def test_resolve_defaults_to_common():
    assert resolve_profile_names({}) == ["common"]


def test_resolve_xuanhuan_from_meta_genre():
    meta = {"genre": ["玄幻"]}
    assert resolve_profile_names(meta) == ["common", "xuanhuan"]


def test_resolve_xianxia_from_secondary_genre():
    meta = {"genre": ["玄幻", "修真文明"]}
    assert resolve_profile_names(meta) == ["common", "xuanhuan", "xianxia"]


def test_resolve_suspense_from_genre():
    meta = {"genre": ["悬疑灵异"]}
    assert resolve_profile_names(meta) == ["common", "suspense"]


def test_explicit_profile_override_is_normalized():
    meta = {"genre": ["玄幻"]}
    assert resolve_profile_names(meta, explicit_profiles=["common", "suspense"]) == ["common", "suspense"]
