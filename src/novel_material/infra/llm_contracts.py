"""LLM 业务响应的基础契约原语。"""

from __future__ import annotations

from typing import Any


class LLMResponseContractError(ValueError):
    """合法 JSON 不符合业务响应契约。"""

    def __init__(self, path: str, expected: str, value: object) -> None:
        self.path = path
        self.expected = expected
        self.actual_type = type(value).__name__
        super().__init__(f"{path} 应为{expected}，实际为 {self.actual_type}")


def require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LLMResponseContractError(path, "对象", value)
    return value


def require_mapping_list(value: object, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LLMResponseContractError(path, "对象数组", value)
    return [require_mapping(item, f"{path}[{index}]") for index, item in enumerate(value)]


def require_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise LLMResponseContractError(path, "字符串", value)
    return value


def require_string_list(value: object, path: str) -> list[str]:
    if not isinstance(value, list):
        raise LLMResponseContractError(path, "字符串数组", value)
    return [require_string(item, f"{path}[{index}]") for index, item in enumerate(value)]


def require_number(value: object, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMResponseContractError(path, "数值", value)
    return value


def require_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LLMResponseContractError(path, "整数", value)
    return value


__all__ = [
    "LLMResponseContractError",
    "require_integer",
    "require_mapping",
    "require_mapping_list",
    "require_number",
    "require_string",
    "require_string_list",
]
