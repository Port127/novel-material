"""人物统计：出场频率统计、分层筛选。

此模块包含人物提取所需的统计函数，
供 characters_core.py 和其他子模块使用。
"""
from collections import Counter

from novel_material.infra.common import is_special_chapter_type


# 分层阈值（可配置）
CHARACTER_THRESHOLDS = {
    "core": 50,       # >= 50 章为核心人物
    "supporting": 10,  # >= 10 章为配角
    "minor": 5         # >= 5 章为次要人物
}

# 分批大小
CHARACTER_BATCH_SIZE = 25  # 每批处理 25 人

# 有效角色类型
VALID_ROLES = ("protagonist", "antagonist", "supporting", "minor")


def _extract_appearance_stats(chapters_data: list) -> dict:
    """统计章节出场人物频率。

    特殊类型章节（afterword/author_note）不参与统计。

    返回：
        dict: {人物名: 出场章数}
    """
    all_chars = []
    for ch in chapters_data:
        # 跳过特殊类型章节
        if is_special_chapter_type(ch.get("type", "normal")):
            continue
        chars = ch.get("characters_appear", [])
        all_chars.extend(chars)
    return dict(Counter(all_chars))


__all__ = [
    "CHARACTER_THRESHOLDS",
    "CHARACTER_BATCH_SIZE",
    "VALID_ROLES",
    "_extract_appearance_stats",
]