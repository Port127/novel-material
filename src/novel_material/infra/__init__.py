"""基础设施模块：LLM 调用、数据库连接、向量计算、进度追踪、配置管理。"""

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
]