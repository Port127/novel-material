"""章级分析上下文参数封装。

核心功能：
- SlidingWindowContextArgs: 封装 build_sliding_window_context 的参数
- load_optional_navigation_context: 只读加载可选前置导航文本

用于简化函数调用，提高可读性。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from novel_material.pipeline.evaluation_models import load_evaluation_navigation


@dataclass
class SlidingWindowContextArgs:
    """滑动窗口上下文参数。"""

    chapter_num: int
    chapters_data: dict[int, dict]
    lines: list[str]
    chapter_index: list[dict]
    evaluation: dict | None = None
    next_preview_chars: int = 500


def load_optional_navigation_context(novel_dir: Path) -> tuple[str, tuple[str, ...]]:
    """加载可选前置导航上下文。

    前置导航由 ``evaluation.yaml`` 提供，但章级分析不应硬依赖它：
    缺失时返回空上下文和诊断码，让调用方继续执行滑动窗口分析。
    """
    navigation = load_evaluation_navigation(novel_dir)
    if navigation is None:
        return "", ("navigation_missing",)

    context_parts = [
        _format_line("类型", "、".join(navigation.novel_type)),
        _format_line("主线", navigation.main_thread_summary),
    ]
    if navigation.core_character_candidates:
        names = "、".join(
            candidate.name for candidate in navigation.core_character_candidates[:5]
        )
        context_parts.append(_format_line("核心人物候选", names))
    if navigation.stage_map:
        stage_lines = [
            f"{item.stage}: {item.central_conflict}"
            for item in navigation.stage_map
            if item.central_conflict
        ]
        context_parts.append(_format_line("阶段地图", "；".join(stage_lines)))
    if navigation.analysis_focus:
        context_parts.append(
            _format_line("分析重点", "、".join(navigation.analysis_focus))
        )

    context = "\n".join(part for part in context_parts if part)
    return context, ()


def _format_line(label: str, value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return f"{label}：{value}"


__all__ = ["SlidingWindowContextArgs", "load_optional_navigation_context"]
