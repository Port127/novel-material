"""人物档案生成：构建人物档案、增量写入。

此模块包含人物档案生成函数和增量写入辅助函数，
供 characters_core.py 使用。
"""
import re
from pathlib import Path

from novel_material.infra.yaml_io import load_yaml, save_yaml


def _build_basic_profile_from_stats(name: str, count: int, role: str, chapters_data: list) -> dict:
    """基于出场统计生成基础人物档案（兜底方案，不调用LLM）。

    Args:
        name: 人物名称
        count: 出场章数
        role: 角色类型
        chapters_data: 章节数据（用于提取首章和关键事件）

    Returns:
        dict: 基础人物档案
    """
    # 从章节数据中提取首次出场章节
    first_chapter = None
    key_events = []

    for ch in chapters_data:
        if name in ch.get("characters_appear", []):
            ch_num = ch.get("chapter", 0)
            if first_chapter is None:
                first_chapter = ch_num
            # 收集关键事件（最多5个）
            event = ch.get("key_event", "")
            if event and len(key_events) < 5:
                key_events.append({"chapter": ch_num, "description": event[:30]})

    profile = {
        "name": name,
        "role": role,
        "description": f"出场 {count} 章，为主要角色之一。",
        "first_appearance_chapter": first_chapter,
        "appearance_count": count,
        "narrative_function": "待补充",
        "relationships": []
    }

    if role in ("protagonist", "antagonist", "supporting"):
        # 核心人物添加 key_events
        profile["key_events"] = key_events

    return profile


def _build_profile_from_character(ch: dict, role: str) -> dict:
    """根据角色类型构建人物档案。

    Args:
        ch: LLM 返回的人物数据
        role: 角色类型

    Returns:
        dict: 人物档案
    """
    if role in ("protagonist", "antagonist", "supporting"):
        return {
            "name": ch.get("name"),
            "role": role,
            "archetype": ch.get("archetype"),
            "moral_spectrum": ch.get("moral_spectrum"),
            "description": ch.get("description"),
            "arc_summary": ch.get("arc_summary"),
            "narrative_function": ch.get("narrative_function"),
            "psychology": ch.get("psychology", {}),
            "first_appearance_chapter": ch.get("first_appearance_chapter"),
            "key_events": ch.get("key_events", [])[:10],
            "relationships": ch.get("relationships", [])
        }
    else:
        return {
            "name": ch.get("name"),
            "role": "minor",
            "description": ch.get("description"),
            "first_appearance_chapter": ch.get("first_appearance_chapter"),
            "narrative_function": ch.get("narrative_function"),
            "relationships": ch.get("relationships", [])
        }


def _save_character_profile(profiles_dir: Path, idx: int, profile: dict, name: str) -> None:
    """保存单个人物小传到独立文件（增量写入）。

    Args:
        profiles_dir: profiles 目录路径
        idx: 人物序号
        profile: 人物档案数据
        name: 人物名称（用于生成文件名）
    """
    # slug 化文件名：只保留字母、数字、中文，其他替换为下划线
    slug = re.sub(r'[^\w一-鿿]', '_', name)
    filename = f"{slug}_{idx:03d}.yaml"
    save_yaml(profiles_dir / filename, profile)


def _load_existing_profiles(char_dir: Path) -> tuple[list, set]:
    """加载已保存的人物小传（断点续传）。

    Args:
        char_dir: characters 目录路径

    Returns:
        tuple: (已保存的人物档案列表, 已保存的人物名称集合)
    """
    profiles_dir = char_dir / "profiles"
    if not profiles_dir.exists():
        return [], set()

    existing_profiles = []
    existing_names = set()

    for f in profiles_dir.glob("*.yaml"):
        try:
            profile = load_yaml(f)
            if profile.get("name"):
                existing_profiles.append(profile)
                existing_names.add(profile["name"])
        except Exception:
            continue

    return existing_profiles, existing_names


__all__ = [
    "_build_basic_profile_from_stats",
    "_build_profile_from_character",
    "_save_character_profile",
    "_load_existing_profiles",
]