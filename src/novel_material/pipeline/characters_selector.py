"""人物分层筛选：基于出场统计筛选候选人。

此模块包含分层筛选函数，
供 characters_core.py 使用。
"""
from novel_material.pipeline.characters_stats import CHARACTER_THRESHOLDS
from novel_material.pipeline.characters_selection import (
    BiographySelection,
    BiographyTarget,
    CharacterSignals,
    build_character_signals,
    select_biography_targets,
)


def _select_candidate_characters(appearance_stats: dict, thresholds: dict | None = None) -> dict:
    """基于出场统计分层筛选候选人。

    Args:
        appearance_stats: 出场统计 {人物名: 出场章数}
        thresholds: 可选的分层阈值，默认使用 CHARACTER_THRESHOLDS

    Returns:
        dict: {
            "core": [(name, count), ...],    # >= 50 章
            "supporting": [...],              # 10-49 章
            "minor": [...]                    # 5-9 章
        }
    """
    if thresholds is None:
        thresholds = CHARACTER_THRESHOLDS

    core_threshold = thresholds.get("core", 50)
    supporting_threshold = thresholds.get("supporting", 10)
    minor_threshold = thresholds.get("minor", 5)

    core = []
    supporting = []
    minor = []

    for name, count in appearance_stats.items():
        if count >= core_threshold:
            core.append((name, count))
        elif count >= supporting_threshold:
            supporting.append((name, count))
        elif count >= minor_threshold:
            minor.append((name, count))

    # 按出场频率排序
    core.sort(key=lambda x: -x[1])
    supporting.sort(key=lambda x: -x[1])
    minor.sort(key=lambda x: -x[1])

    return {
        "core": core,
        "supporting": supporting,
        "minor": minor
    }


__all__ = [
    "BiographySelection",
    "BiographyTarget",
    "CharacterSignals",
    "_select_candidate_characters",
    "build_character_signals",
    "select_biography_targets",
]
