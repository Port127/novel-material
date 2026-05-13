"""标签管理模块。

提供标签加载、校验、领域定位、审核等功能。
"""

from .validate import validate_tag, validate_tags_batch, check_dimension_usage, check_dimension, suggest_expand
from .resolve import resolve_tag_domain, suggest_genre_for_tag
from .load import load_tags_for_genre, format_tags_for_prompt, get_all_genres

__all__ = [
    "validate_tag",
    "validate_tags_batch",
    "check_dimension_usage",
    "check_dimension",
    "suggest_expand",
    "resolve_tag_domain",
    "suggest_genre_for_tag",
    "load_tags_for_genre",
    "format_tags_for_prompt",
    "get_all_genres",
]