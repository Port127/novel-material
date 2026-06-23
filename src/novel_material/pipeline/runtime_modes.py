"""Runtime modes for unattended pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass, replace

from novel_material.infra.config import get_settings


STANDARD_INSIGHT_CHAPTER_LIMIT_DEFAULT = 100


@dataclass(frozen=True)
class RuntimeMode:
    """Pipeline runtime mode with explicit time/quality trade-offs."""

    name: str
    include_core_insights: bool
    include_deep_insights: bool
    block_on_deep_insights: bool
    insight_depth: str
    insight_batch_size: int
    key_chapter_rate: float
    core_insight_chapter_limit: int | None


_MODES = {
    "fast": RuntimeMode(
        name="fast",
        include_core_insights=False,
        include_deep_insights=False,
        block_on_deep_insights=False,
        insight_depth="none",
        insight_batch_size=0,
        key_chapter_rate=0.0,
        core_insight_chapter_limit=0,
    ),
    "standard": RuntimeMode(
        name="standard",
        include_core_insights=True,
        include_deep_insights=False,
        block_on_deep_insights=False,
        insight_depth="core",
        insight_batch_size=20,
        key_chapter_rate=0.0,
        core_insight_chapter_limit=STANDARD_INSIGHT_CHAPTER_LIMIT_DEFAULT,
    ),
    "deep": RuntimeMode(
        name="deep",
        include_core_insights=True,
        include_deep_insights=True,
        block_on_deep_insights=True,
        insight_depth="deep",
        insight_batch_size=10,
        key_chapter_rate=0.2,
        core_insight_chapter_limit=None,
    ),
}


def get_runtime_mode(name: str | None) -> RuntimeMode:
    """Return a runtime mode by name, defaulting to standard."""
    mode_name = name or "standard"
    if mode_name not in _MODES:
        allowed = ", ".join(sorted(_MODES))
        raise ValueError(f"未知运行模式: {mode_name}，可选: {allowed}")
    mode = _MODES[mode_name]
    if mode_name != "standard":
        return mode

    value = get_settings().get(
        "INSIGHTS_STANDARD_CHAPTER_LIMIT",
        STANDARD_INSIGHT_CHAPTER_LIMIT_DEFAULT,
    )
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(
            "INSIGHTS_STANDARD_CHAPTER_LIMIT 必须是正整数，"
            f"实际为: {value!r}"
        )
    return replace(mode, core_insight_chapter_limit=value)
