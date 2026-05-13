"""章级分析加载参数封装。

核心功能：
- AnalysisContextArgs: 封装 build_analysis_context 的参数

用于简化函数调用，提高可读性。
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AnalysisContextArgs:
    """分析上下文参数。"""
    novel_dir: Path
    config: dict
    chapters_data: list | None = None
    material_id: str = ""
    summary_tokens_key: str = "outline_summary_tokens"
    fallback_chars: int = 8000


__all__ = ["AnalysisContextArgs"]