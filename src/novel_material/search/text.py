"""中文词法检索的确定性文本构造与分词。"""

from collections.abc import Iterable, Mapping
from typing import Any
import warnings

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
    )
    import jieba


def _flatten_parts(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            yield normalized
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _flatten_parts(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            yield from _flatten_parts(nested)
        return
    normalized = str(value).strip()
    if normalized:
        yield normalized


def build_search_text(*parts: Any) -> str:
    """按参数顺序递归展开可检索字段。"""
    return " ".join(
        text
        for part in parts
        for text in _flatten_parts(part)
    )


def tokenize_for_search(text: str) -> str:
    """保留原短语并生成适用于 PostgreSQL simple 配置的词项。"""
    phrase = text.strip()
    if not phrase:
        return ""

    segmented = [
        token.strip()
        for token in jieba.cut(phrase, cut_all=False)
        if token.strip()
    ]
    tokens = [phrase, *segmented]
    tokens.extend(
        left + right
        for left, right in zip(segmented, segmented[1:])
        if _is_single_cjk(left) and _is_single_cjk(right)
    )
    return " ".join(dict.fromkeys(tokens))


def _is_single_cjk(token: str) -> bool:
    return len(token) == 1 and "\u4e00" <= token <= "\u9fff"
