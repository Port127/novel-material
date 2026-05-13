"""素材管理模块。"""

from .import_material import import_material
from .delete import delete_material

__all__ = [
    "import_material",
    "delete_material",
]