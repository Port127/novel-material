"""Schema 契约层：字段定义与阈值加载。

导出：
- FieldSchema: 字段契约类
- load_field: 加载单个字段契约
- get_threshold: 获取非字段阈值
"""

from novel_material.schema.fields_loader import FieldSchema, load_field, load_all_fields
from novel_material.schema.thresholds import get_threshold

__all__ = [
    "FieldSchema",
    "load_field",
    "load_all_fields",
    "get_threshold",
]