"""章级分析上下文参数封装。

核心功能：
- SlidingWindowContextArgs: 封装 build_sliding_window_context 的参数

用于简化函数调用，提高可读性。
"""

from dataclasses import dataclass


@dataclass
class SlidingWindowContextArgs:
    """滑动窗口上下文参数。"""
    chapter_num: int
    chapters_data: dict[int, dict]
    lines: list[str]
    chapter_index: list[dict]
    evaluation: dict | None = None
    next_preview_chars: int = 500


__all__ = ["SlidingWindowContextArgs"]