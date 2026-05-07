"""流水线模块：数据处理流水线。"""

from .preprocess import preprocess, preprocess_text
from .loader import load_chapters_data, build_summary_pool
from .ingest import ingest_file, generate_material_id
from .analyze import chapter_analyze
from .refine import refine, refine_outline, refine_characters, refine_tags
from .outline import generate_outline, generate_simple_acts
from .worldbuilding import generate_worldbuilding
from .characters import generate_characters
from .tags import generate_tags

__all__ = [
    "preprocess",
    "preprocess_text",
    "load_chapters_data",
    "build_summary_pool",
    "ingest_file",
    "generate_material_id",
    "chapter_analyze",
    "refine",
    "refine_outline",
    "refine_characters",
    "refine_tags",
    "generate_outline",
    "generate_simple_acts",
    "generate_worldbuilding",
    "generate_characters",
    "generate_tags",
]