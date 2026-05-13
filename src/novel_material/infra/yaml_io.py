"""统一 YAML 文件读写服务。

核心功能：
- load_yaml: 加载 YAML 文件，文件不存在返回空字典
- save_yaml: 保存 YAML 文件
- load_yaml_list: 加载 YAML 列表格式

统一编码 utf-8，统一错误处理。
"""

import yaml
from pathlib import Path


def load_yaml(path: Path | str) -> dict:
    """加载 YAML 文件，返回字典。

    Args:
        path: 文件路径

    Returns:
        dict: YAML 内容，文件不存在返回空字典

    Raises:
        yaml.YAMLError: YAML 解析错误
    """
    path = Path(path)
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data if isinstance(data, dict) else {}


def save_yaml(path: Path | str, data: dict | list) -> None:
    """保存 YAML 文件。

    Args:
        path: 文件路径
        data: 要保存的数据（字典或列表）
    """
    path = Path(path)
    # 确保父目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def load_yaml_list(path: Path | str) -> list:
    """加载 YAML 文件，返回列表。

    Args:
        path: 文件路径

    Returns:
        list: YAML 内容，文件不存在返回空列表

    Raises:
        yaml.YAMLError: YAML 解析错误
    """
    path = Path(path)
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data if isinstance(data, list) else []


__all__ = [
    "load_yaml",
    "save_yaml",
    "load_yaml_list",
]