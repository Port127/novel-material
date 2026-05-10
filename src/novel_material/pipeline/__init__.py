"""流水线模块：数据处理流水线。"""

from .preprocess import preprocess, preprocess_text
from .loader import load_chapters_data, build_summary_pool
from .ingest import ingest_file, generate_material_id
from .analyze import chapter_analyze
from .infer import infer_key_plot_points
from novel_material.infra.constants import KEY_PLOT_POINT_VALUES
from .refine import refine, refine_outline, refine_characters, refine_tags
from .outline import generate_outline, generate_simple_acts
from .worldbuilding import generate_worldbuilding
from .characters import generate_characters
from .tags import generate_tags
from .progress import (
    get_pipeline_progress,
    print_pipeline_status,
    get_next_pending_stage,
    PIPELINE_STAGES,
    get_pipeline_stages,
    calculate_total_stages,
    calculate_current_stage,
)
from .evaluate import run_evaluation

__all__ = [
    "preprocess",
    "preprocess_text",
    "load_chapters_data",
    "build_summary_pool",
    "ingest_file",
    "generate_material_id",
    "chapter_analyze",
    "infer_key_plot_points",
    "KEY_PLOT_POINT_VALUES",
    "refine",
    "refine_outline",
    "refine_characters",
    "refine_tags",
    "generate_outline",
    "generate_simple_acts",
    "generate_worldbuilding",
    "generate_characters",
    "generate_tags",
    "get_pipeline_progress",
    "print_pipeline_status",
    "get_next_pending_stage",
    "PIPELINE_STAGES",
    "get_pipeline_stages",
    "calculate_total_stages",
    "calculate_current_stage",
    "run_evaluation",
]