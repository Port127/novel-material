"""Runtime modes for unattended pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass


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


_MODES = {
    "fast": RuntimeMode(
        name="fast",
        include_core_insights=False,
        include_deep_insights=False,
        block_on_deep_insights=False,
        insight_depth="none",
        insight_batch_size=0,
        key_chapter_rate=0.0,
    ),
    "standard": RuntimeMode(
        name="standard",
        include_core_insights=True,
        include_deep_insights=False,
        block_on_deep_insights=False,
        insight_depth="core",
        insight_batch_size=20,
        key_chapter_rate=0.0,
    ),
    "deep": RuntimeMode(
        name="deep",
        include_core_insights=True,
        include_deep_insights=True,
        block_on_deep_insights=True,
        insight_depth="deep",
        insight_batch_size=10,
        key_chapter_rate=0.2,
    ),
}


def get_runtime_mode(name: str | None) -> RuntimeMode:
    """Return a runtime mode by name, defaulting to standard."""
    mode_name = name or "standard"
    if mode_name not in _MODES:
        allowed = ", ".join(sorted(_MODES))
        raise ValueError(f"未知运行模式: {mode_name}，可选: {allowed}")
    return _MODES[mode_name]
