"""流水线模块：数据处理流水线。

公共接口（推荐使用）：
- ingest_file：素材导入入口
- chapter_analyze：章节分析入口
- generate_outline：大纲生成入口
- generate_worldbuilding：世界观提取入口
- generate_characters：人物提取入口
- generate_tags：标签生成入口
- refine：精修入口
- run_evaluation：评估入口
- get_pipeline_progress：进度查询
- print_pipeline_status：进度打印
- get_next_pending_stage：获取下一待处理阶段

内部接口（从具体子模块导入）：
- preprocess, preprocess_text: pipeline.preprocess
- load_chapters_data, build_summary_pool: pipeline.loader
- infer_key_plot_points: pipeline.infer
- refine_outline, refine_characters, refine_tags: pipeline.refine
- generate_simple_acts: pipeline.outline_acts
- PIPELINE_STAGES, get_pipeline_stages: pipeline.progress
"""

from .ingest import ingest_file
from .analyze import chapter_analyze
from .outline import generate_outline
from .worldbuilding import generate_worldbuilding
from .characters import generate_characters
from .tags import generate_tags
from .refine import refine
from .evaluate import run_evaluation
from .progress import (
    get_pipeline_progress,
    print_pipeline_status,
    get_next_pending_stage,
)

__all__ = [
    # 公共接口
    "ingest_file",
    "chapter_analyze",
    "generate_outline",
    "generate_worldbuilding",
    "generate_characters",
    "generate_tags",
    "refine",
    "run_evaluation",
    "get_pipeline_progress",
    "print_pipeline_status",
    "get_next_pending_stage",
]