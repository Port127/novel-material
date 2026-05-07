"""素材管理模块。"""

from .import_material import import_material, generate_material_id
from .delete import delete_material

__all__ = [
    "import_material",
    "generate_material_id",
    "delete_material",
]