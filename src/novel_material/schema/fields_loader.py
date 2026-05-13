"""字段契约加载器：从 fields.yaml 读取字段定义。"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

# 契约文件路径
_FIELDS_FILE = Path(__file__).parent / "fields.yaml"


@dataclass
class FieldSchema:
    """字段契约定义。"""
    name: str
    description: str
    min_length: int | None = None
    max_length: int | None = None
    validate_in: list[Literal["prompt", "schema", "quality"]] = field(default_factory=list)

    @classmethod
    def load(cls, field_name: str) -> "FieldSchema":
        """加载单个字段契约。

        Args:
            field_name: 字段名称（如 "summary"）

        Returns:
            FieldSchema 实例

        Raises:
            KeyError: 字段不存在
        """
        fields = _load_fields_yaml()
        if field_name not in fields:
            raise KeyError(f"字段 '{field_name}' 不存在于 fields.yaml")

        data = fields[field_name]
        return cls(
            name=field_name,
            description=data.get("description", ""),
            min_length=data.get("min_length"),
            max_length=data.get("max_length"),
            validate_in=data.get("validate_in", []),
        )

    @classmethod
    def load_all(cls) -> list["FieldSchema"]:
        """加载所有字段契约。

        只返回有 validate_in 的字段（表示需要校验）。

        Returns:
            FieldSchema 实例列表
        """
        fields = _load_fields_yaml()
        result = []
        for name, data in fields.items():
            # 只加载有 validate_in 的字段
            if "validate_in" in data:
                result.append(cls(
                    name=name,
                    description=data.get("description", ""),
                    min_length=data.get("min_length"),
                    max_length=data.get("max_length"),
                    validate_in=data.get("validate_in", []),
                ))
        return result


def load_field(field_name: str) -> FieldSchema:
    """加载单个字段契约（便捷函数）。"""
    return FieldSchema.load(field_name)


def load_all_fields() -> list[FieldSchema]:
    """加载所有字段契约（便捷函数）。"""
    return FieldSchema.load_all()


def _load_fields_yaml() -> dict:
    """加载 fields.yaml 文件内容。"""
    if not _FIELDS_FILE.exists():
        raise FileNotFoundError(f"契约文件不存在: {_FIELDS_FILE}")

    with open(_FIELDS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # 过滤掉非字段定义（如 character_thresholds）
    fields = {}
    for key, value in data.items():
        if isinstance(value, dict) and "description" in value:
            fields[key] = value

    return fields