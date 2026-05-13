"""阈值加载器：从 fields.yaml 读取非字段阈值（常量）。"""

import yaml
from pathlib import Path

# 契约文件路径
_FIELDS_FILE = Path(__file__).parent / "fields.yaml"

# 缓存已加载的阈值
_thresholds_cache: dict | None = None


def get_threshold(threshold_name: str) -> int | dict:
    """获取非字段阈值。

    Args:
        threshold_name: 阈值名称（如 "character_thresholds"、"sample_threshold"）

    Returns:
        阈值值（整数或字典）

    Raises:
        KeyError: 阈值不存在

    Examples:
        >>> get_threshold("character_thresholds")["core"]
        50
        >>> get_threshold("sample_threshold")
        200
    """
    thresholds = _load_thresholds_yaml()
    if threshold_name not in thresholds:
        raise KeyError(f"阈值 '{threshold_name}' 不存在于 fields.yaml")

    data = thresholds[threshold_name]
    # 如果有 value 字段，返回 value；否则返回整个字典（如 character_thresholds）
    if "value" in data:
        return data["value"]
    return {k: v for k, v in data.items() if k != "description"}


def _load_thresholds_yaml() -> dict:
    """加载 fields.yaml 中的阈值部分。"""
    global _thresholds_cache

    if _thresholds_cache is not None:
        return _thresholds_cache

    if not _FIELDS_FILE.exists():
        raise FileNotFoundError(f"契约文件不存在: {_FIELDS_FILE}")

    with open(_FIELDS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # 提取非字段定义（没有 validate_in 的条目）
    thresholds = {}
    for key, value in data.items():
        if isinstance(value, dict) and "validate_in" not in value:
            thresholds[key] = value

    _thresholds_cache = thresholds
    return thresholds