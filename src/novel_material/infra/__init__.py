"""基础设施模块：LLM 调用、数据库连接、向量计算、进度追踪、配置管理、公共函数。"""

from .config import (
    PROJECT_ROOT,
    DATA_DIR,
    NOVELS_DIR,
    CONFIG_DIR,
    SCHEMAS_DIR,
    INDEX_FILE,
    TAGS_VIEW_FILE,
    VALID_STATUSES,
    update_meta_status,
)
from .llm import (
    load_config,
    list_available_providers,
    call_llm,
    truncate_to_tokens,
    get_api_stats,
    reset_api_stats,
)
from .embedding import (
    load_embedding_config,
    get_embedding,
    get_embeddings_batch,
)
from .progress import (
    get_pipeline_logger,
    StageTracker,
    PipelineRunner,
    stage_context,
)
from .common import (
    # 常量
    KEY_PLOT_POINT_VALUES,
    NOVEL_TYPE_VALUES,
    TENSION_CHANGE_VALUES,
    HOOK_TYPE_VALUES,
    SPECIAL_CHAPTER_TYPES,
    VALID_CHAPTER_TYPES,
    # 公共函数
    is_special_chapter_type,
    is_valid_chapter_type,
    filter_normal_chapters,
    generate_material_id,
)

__all__ = [
    # config
    "PROJECT_ROOT",
    "DATA_DIR",
    "NOVELS_DIR",
    "CONFIG_DIR",
    "SCHEMAS_DIR",
    "INDEX_FILE",
    "TAGS_VIEW_FILE",
    "VALID_STATUSES",
    "update_meta_status",
    # llm
    "load_config",
    "list_available_providers",
    "call_llm",
    "truncate_to_tokens",
    "get_api_stats",
    "reset_api_stats",
    # embedding
    "load_embedding_config",
    "get_embedding",
    "get_embeddings_batch",
    # progress
    "get_pipeline_logger",
    "StageTracker",
    "PipelineRunner",
    "stage_context",
    # common - 常量
    "KEY_PLOT_POINT_VALUES",
    "NOVEL_TYPE_VALUES",
    "TENSION_CHANGE_VALUES",
    "HOOK_TYPE_VALUES",
    "SPECIAL_CHAPTER_TYPES",
    "VALID_CHAPTER_TYPES",
    # common - 公共函数
    "is_special_chapter_type",
    "is_valid_chapter_type",
    "filter_normal_chapters",
    "generate_material_id",
]