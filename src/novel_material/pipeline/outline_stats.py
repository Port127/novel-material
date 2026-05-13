"""大纲统计：张力分布、悬念章节、章节功能统计。

此模块包含大纲生成所需的统计函数，
供 outline_core.py 和 outline_acts.py 使用。
"""
from collections import Counter

from novel_material.infra.common import is_special_chapter_type


def _extract_outline_stats(chapters_data: list) -> dict:
    """统计大纲相关数据：张力分布、悬念章节、章节功能。

    特殊类型章节（afterword/author_note）不参与统计。

    返回：
        dict: {
            "tension_distribution": {张力等级: 章数},
            "high_tension_chapters": [高张力章节号列表],
            "suspense_chapters": [悬念章节号列表],
            "function_distribution": {功能: 章数}
        }
    """
    tension_counts = Counter()
    high_tension_chapters = []  # 张力 >= 4
    suspense_chapters = []  # 有"悬念"功能的章节
    function_counts = Counter()

    for ch in chapters_data:
        # 跳过特殊类型章节
        if is_special_chapter_type(ch.get("type", "normal")):
            continue

        ch_num = ch.get("chapter", 0)
        tension = ch.get("tension_level", 0)
        functions = ch.get("chapter_functions", [])

        tension_counts[tension] += 1

        if tension >= 4:
            high_tension_chapters.append(ch_num)

        if any("悬念" in f for f in functions):
            suspense_chapters.append(ch_num)

        function_counts.update(functions)

    return {
        "tension_distribution": dict(sorted(tension_counts.items())),
        "high_tension_chapters": sorted(high_tension_chapters),
        "suspense_chapters": sorted(suspense_chapters),
        "function_distribution": dict(function_counts.most_common(20))
    }


__all__ = ["_extract_outline_stats"]