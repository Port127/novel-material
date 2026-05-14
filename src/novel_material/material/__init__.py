"""素材管理模块。"""

from .import_material import import_material
from .delete import delete_material
from .classify import (
    classify_book,
    get_status,
    load_novel_index,
    load_material_index,
    save_material_index,
    load_progress,
    save_progress,
    CLASSIFY_INDEX_FILE,
    CLASSIFY_PROGRESS_FILE,
)
from .classify_prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, VALID_GENRES

__all__ = [
    "import_material",
    "delete_material",
    # classify
    "classify_book",
    "get_status",
    "load_novel_index",
    "load_material_index",
    "save_material_index",
    "load_progress",
    "save_progress",
    "CLASSIFY_INDEX_FILE",
    "CLASSIFY_PROGRESS_FILE",
    # classify_prompt
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
    "VALID_GENRES",
]