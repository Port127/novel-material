"""自适应主要人物小传目标选择。"""

from __future__ import annotations

from dataclasses import dataclass

from novel_material.pipeline.characters_stats import _extract_appearance_stats
from novel_material.pipeline.evaluation_models import EvaluationNavigation
from novel_material.schema import get_threshold


@dataclass(frozen=True)
class CharacterSignals:
    """用于主要人物小传选择的多维信号。"""

    appearance_counts: dict[str, int]
    chapter_span: dict[str, tuple[int, int]]
    key_event_counts: dict[str, int]
    relationship_degree: dict[str, int]
    navigation: EvaluationNavigation


@dataclass(frozen=True)
class BiographyTarget:
    """被选为完整小传目标的人物。"""

    name: str
    score: float
    reasons: tuple[str, ...]
    appearance_count: int
    role_hint: str = "supporting"


@dataclass(frozen=True)
class BiographySelection:
    """完整小传目标选择结果。"""

    targets: tuple[BiographyTarget, ...]
    selection_reason: str
    qualified_count: int


def select_biography_targets(signals: CharacterSignals) -> BiographySelection:
    """根据多维信号选择 5–12 名完整小传目标。"""
    limits = _biography_limits()
    minor_threshold = int(get_threshold("character_thresholds").get("minor", 5))
    navigation_confidence = {
        candidate.name: candidate.confidence
        for candidate in signals.navigation.core_character_candidates
    }
    names = _qualified_names(signals, minor_threshold)
    targets = tuple(
        sorted(
            (_score_target(name, signals, navigation_confidence) for name in names),
            key=lambda item: (-item.score, -item.appearance_count, item.name),
        )
    )

    if len(targets) < limits["min"]:
        return BiographySelection(
            targets=targets,
            selection_reason="fewer_than_minimum",
            qualified_count=len(targets),
        )

    return BiographySelection(
        targets=targets[: limits["max"]],
        selection_reason="enough_candidates",
        qualified_count=len(targets),
    )


def build_character_signals(
    chapters_data: list[dict],
    navigation: EvaluationNavigation,
) -> CharacterSignals:
    """从章级分析数据和前置导航派生人物选择信号。"""
    appearance_counts = _extract_appearance_stats(chapters_data)
    chapter_span: dict[str, tuple[int, int]] = {}
    key_event_counts: dict[str, int] = {name: 0 for name in appearance_counts}
    coappearances: dict[str, set[str]] = {name: set() for name in appearance_counts}

    for chapter in chapters_data:
        chapter_num = _chapter_number(chapter)
        characters = _chapter_characters(chapter)
        key_event = str(chapter.get("key_event", "") or "")

        for name in characters:
            start, end = chapter_span.get(name, (chapter_num, chapter_num))
            chapter_span[name] = (min(start, chapter_num), max(end, chapter_num))
            if name in key_event:
                key_event_counts[name] = key_event_counts.get(name, 0) + 1
            coappearances.setdefault(name, set()).update(
                other for other in characters if other != name
            )

    relationship_degree = {
        name: len(coappearances.get(name, set())) for name in appearance_counts
    }
    return CharacterSignals(
        appearance_counts=appearance_counts,
        chapter_span=chapter_span,
        key_event_counts=key_event_counts,
        relationship_degree=relationship_degree,
        navigation=navigation,
    )


def _qualified_names(signals: CharacterSignals, minor_threshold: int) -> tuple[str, ...]:
    navigation_names = {
        candidate.name for candidate in signals.navigation.core_character_candidates
    }
    names = {
        name
        for name, count in signals.appearance_counts.items()
        if count >= minor_threshold
    }
    names.update(
        name
        for name in navigation_names
        if signals.appearance_counts.get(name, 0) > 0
    )
    return tuple(names)


def _score_target(
    name: str,
    signals: CharacterSignals,
    navigation_confidence: dict[str, float],
) -> BiographyTarget:
    appearance_score = _normalize(
        signals.appearance_counts.get(name, 0),
        signals.appearance_counts.values(),
    )
    span_score = _span_width(signals.chapter_span.get(name)) / max(
        _max_span_width(signals.chapter_span),
        1,
    )
    key_event_score = _normalize(
        signals.key_event_counts.get(name, 0),
        signals.key_event_counts.values(),
    )
    relationship_score = _normalize(
        signals.relationship_degree.get(name, 0),
        signals.relationship_degree.values(),
    )
    navigation_score = navigation_confidence.get(name, 0.0)
    score = (
        appearance_score * 0.35
        + span_score * 0.20
        + key_event_score * 0.20
        + relationship_score * 0.10
        + navigation_score * 0.15
    )
    return BiographyTarget(
        name=name,
        score=round(score, 6),
        reasons=_selection_reasons(
            name,
            signals,
            navigation_confidence,
            appearance_score,
            span_score,
            key_event_score,
            relationship_score,
        ),
        appearance_count=signals.appearance_counts.get(name, 0),
        role_hint=_role_hint(name, signals, navigation_confidence),
    )


def _selection_reasons(
    name: str,
    signals: CharacterSignals,
    navigation_confidence: dict[str, float],
    appearance_score: float,
    span_score: float,
    key_event_score: float,
    relationship_score: float,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if appearance_score > 0:
        reasons.append(f"出场{signals.appearance_counts.get(name, 0)}章")
    if span_score >= 0.5:
        reasons.append("贯穿跨度较长")
    if key_event_score > 0:
        reasons.append(f"参与关键事件{signals.key_event_counts.get(name, 0)}次")
    if relationship_score > 0:
        reasons.append(f"关系中心度{signals.relationship_degree.get(name, 0)}")
    if name in navigation_confidence:
        reasons.append(f"前置导航候选{navigation_confidence[name]:.2f}")
    return tuple(reasons)


def _role_hint(
    name: str,
    signals: CharacterSignals,
    navigation_confidence: dict[str, float],
) -> str:
    if navigation_confidence.get(name, 0.0) >= 0.8:
        return "protagonist"
    core_threshold = int(get_threshold("character_thresholds").get("core", 50))
    if signals.appearance_counts.get(name, 0) >= core_threshold:
        return "protagonist"
    supporting_threshold = int(
        get_threshold("character_thresholds").get("supporting", 10)
    )
    if signals.appearance_counts.get(name, 0) >= supporting_threshold:
        return "supporting"
    return "minor"


def _biography_limits() -> dict[str, int]:
    try:
        config = get_threshold("major_character_biography")
    except KeyError:
        return {"min": 5, "max": 12}
    return {
        "min": int(config.get("min", 5)),
        "max": int(config.get("max", 12)),
    }


def _normalize(value: int, values: object) -> float:
    value_list = list(values)
    maximum = max(value_list, default=0)
    if maximum <= 0:
        return 0.0
    return value / maximum


def _span_width(span: tuple[int, int] | None) -> int:
    if span is None:
        return 0
    return max(0, span[1] - span[0] + 1)


def _max_span_width(chapter_span: dict[str, tuple[int, int]]) -> int:
    return max((_span_width(span) for span in chapter_span.values()), default=0)


def _chapter_number(chapter: dict) -> int:
    try:
        return int(chapter.get("chapter", 0))
    except (TypeError, ValueError):
        return 0


def _chapter_characters(chapter: dict) -> tuple[str, ...]:
    characters = chapter.get("characters_appear", ())
    if not isinstance(characters, (list, tuple)):
        return ()
    return tuple(
        item.strip() for item in characters if isinstance(item, str) and item.strip()
    )


__all__ = [
    "BiographySelection",
    "BiographyTarget",
    "CharacterSignals",
    "build_character_signals",
    "select_biography_targets",
]
