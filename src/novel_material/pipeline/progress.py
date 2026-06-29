"""流水线进度检查：检查各阶段完成情况，支持断点续传。"""
import os
import psycopg2
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path
from rich.console import Console
from rich.table import Table

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml, load_yaml_list
from novel_material.analysis_profiles import load_profiles, merge_profiles
from novel_material.pipeline.profile_resolver import resolve_profile_names
from novel_material.pipeline.evaluation_models import load_evaluation_navigation
from novel_material.validation.insights import validate_insight_file
from novel_material.runtime.contracts import (
    Diagnostic,
    ProgressCounts,
    RunStatus,
    StageResult,
)
from novel_material.pipeline.state import PipelineStateStore

load_dotenv()
console = Console()


# 流水线阶段定义（按执行顺序）
PIPELINE_STAGES = [
    ("入库", "ingested", True),           # (显示名, 进度键, 是否计入总阶段数)
    ("总体评估", "evaluation", False),    # 可选阶段，不计入总阶段数
    ("章级分析", "analyzed", True),
    ("大纲", "outline", True),
    ("世界观", "worldbuilding", True),
    ("人物", "characters", True),
    ("标签", "tags", True),
    ("深度分析", "insights", True),
    ("精调", "refined", True),
    ("数据库同步", "synced", False),      # 不计入总阶段数，仅用于进度状态表
]

# 子流水线阶段数（供 CLI 和 pipeline 模块使用）
EVALUATION_STAGES = 5          # 总体评估：5个批次
CHARACTERS_STAGES = 3          # 人物提取：核心/配角/次要（向量化单独阶段）
WORLDBUILDING_STAGES = 1       # 世界观：提取（向量化单独阶段）
OUTLINE_STAGES = 3             # 大纲：前提/幕序列/beats


@dataclass(frozen=True)
class DatabaseProbeResult:
    status: str
    diagnostic: Diagnostic | None = None


@dataclass(frozen=True)
class PipelineInspection:
    exists: bool
    legacy_unverified: bool
    stages: dict[str, StageResult]
    database: DatabaseProbeResult


def probe_database_status(material_id: str) -> DatabaseProbeResult:
    """返回 synced/not_synced/unknown 三态数据库状态。"""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM novels WHERE material_id = %s", [material_id])
                synced = cur.fetchone() is not None
        finally:
            conn.close()
    except Exception as exc:
        return DatabaseProbeResult(
            status="unknown",
            diagnostic=Diagnostic(
                code="database_unreachable",
                message=f"数据库状态不可用: {type(exc).__name__}",
                severity="warning",
                retryable=True,
            ),
        )
    return DatabaseProbeResult(status="synced" if synced else "not_synced")


def inspect_pipeline_state(
    material_id: str,
    *,
    novels_dir: Path = NOVELS_DIR,
) -> PipelineInspection:
    """读取新 sidecar；旧素材仅执行只读事实校验。"""
    novel_dir = novels_dir / material_id
    database = probe_database_status(material_id)
    if not novel_dir.exists():
        return PipelineInspection(False, False, {}, database)

    if (novel_dir / "runs").exists():
        persisted = PipelineStateStore(novel_dir).read_latest()
        return PipelineInspection(
            True,
            False,
            {stage.name: stage for stage in persisted.stages},
            database,
        )

    meta_file = novel_dir / "meta.yaml"
    meta = load_yaml(meta_file) if meta_file.exists() else {}
    stages = {
        "ingest": _legacy_presence_stage("ingest", (novel_dir / "chapter_index.yaml").exists()),
        "evaluation": _legacy_presence_stage(
            "evaluation",
            _has_complete_evaluation(novel_dir),
        ),
        "analyze": _legacy_presence_stage("analyze", (novel_dir / "chapters.yaml").exists()),
        "outline": _legacy_presence_stage("outline", (novel_dir / "outline/_index.yaml").exists()),
        "worldbuilding": _legacy_presence_stage("worldbuilding", (novel_dir / "worldbuilding/_index.yaml").exists()),
        "characters": _legacy_presence_stage("characters", (novel_dir / "characters/_index.yaml").exists()),
        "tags": _legacy_presence_stage("tags", (novel_dir / "tags.yaml").exists()),
        "insights": _inspect_legacy_insights(novel_dir, meta),
        "refine": _legacy_presence_stage("refine", meta.get("refined_at") is not None),
        "sync": _legacy_presence_stage("sync", database.status == "synced"),
    }
    return PipelineInspection(True, True, stages, database)


def next_pending_stage(
    inspection: PipelineInspection,
    *,
    include_navigation: bool = False,
) -> str | None:
    """按公开流水线顺序返回第一个非成功阶段。"""
    if not inspection.exists:
        return None
    order = (
        ("ingest",)
        + (("evaluation",) if include_navigation else ())
        + (
            "analyze",
            "outline",
            "worldbuilding",
            "characters",
            "tags",
            "insights",
            "refine",
            "sync",
        )
    )
    for name in order:
        stage = inspection.stages.get(name)
        if stage is None or stage.status is not RunStatus.SUCCESS:
            return name
    return None


def _legacy_presence_stage(name: str, present: bool) -> StageResult:
    return StageResult(
        stage_id=f"legacy-{name}",
        name=name,
        status=RunStatus.SUCCESS if present else RunStatus.PENDING,
    )


def _has_complete_evaluation(novel_dir: Path) -> bool:
    try:
        return load_evaluation_navigation(novel_dir) is not None
    except (TypeError, ValueError):
        return False


def _inspect_legacy_insights(novel_dir: Path, meta: dict) -> StageResult:
    chapter_index_file = novel_dir / "chapter_index.yaml"
    chapters = load_yaml_list(chapter_index_file) if chapter_index_file.exists() else []
    expected = len(chapters)
    profile = merge_profiles(load_profiles(resolve_profile_names(meta)))
    succeeded = 0
    failed = 0
    for chapter in chapters:
        number = chapter.get("chapter") if isinstance(chapter, dict) else None
        path = novel_dir / "chapter_insights" / f"{number:04d}.yaml" if isinstance(number, int) else None
        if path is not None and path.exists() and not validate_insight_file(path, profile):
            succeeded += 1
        else:
            failed += 1
    status = RunStatus.SUCCESS if expected > 0 and failed == 0 else RunStatus.DEGRADED
    return StageResult(
        stage_id="legacy-insights",
        name="insights",
        status=status,
        counts=ProgressCounts(
            expected=expected,
            processed=expected,
            succeeded=succeeded,
            failed=failed,
            remaining=0,
        ),
    )


def get_pipeline_stages(include_evaluation: bool = False, include_insights: bool = True) -> list:
    """获取流水线阶段列表（不含数据库同步）。

    Args:
        include_evaluation: 是否包含总体评估阶段
        include_insights: 是否包含题材感知深度分析阶段

    Returns:
        list: 阶段列表 [(显示名, 进度键), ...]
    """
    return [
        (name, key)
        for name, key, counted in PIPELINE_STAGES
        if (counted or (key == "evaluation" and include_evaluation))
        and (include_insights or key != "insights")
    ]


def has_complete_insights(novel_dir: Path) -> bool:
    """仅当每个索引章节都有 schema 合法的 insight 时返回 True。"""
    chapter_index_file = novel_dir / "chapter_index.yaml"
    if not chapter_index_file.exists():
        return False
    chapter_index = load_yaml_list(chapter_index_file)
    total = len(chapter_index)
    if total == 0:
        return False
    insights_dir = novel_dir / "chapter_insights"
    if not insights_dir.exists():
        return False
    meta_file = novel_dir / "meta.yaml"
    meta = load_yaml(meta_file) if meta_file.exists() else {}
    profile = merge_profiles(load_profiles(resolve_profile_names(meta)))
    for chapter in chapter_index:
        if not isinstance(chapter, dict) or not isinstance(chapter.get("chapter"), int):
            return False
        path = insights_dir / f"{chapter['chapter']:04d}.yaml"
        if not path.exists() or validate_insight_file(path, profile):
            return False
    return True


def get_pipeline_progress(material_id: str) -> dict:
    """检查各阶段完成情况。

    Returns:
        dict: 包含各阶段完成状态的字典
    """
    novel_dir = NOVELS_DIR / material_id

    if not novel_dir.exists():
        return {"exists": False}

    meta_file = novel_dir / "meta.yaml"
    meta = {}
    if meta_file.exists():
        meta = load_yaml(meta_file)

    # 检查章级分析是否完成
    # 优先检查 chapters/ 目录（分析过程中每章独立保存）
    # 其次检查 chapters.yaml（分析完成后合并的快照）
    analyzed = False
    chapter_index_file = novel_dir / "chapter_index.yaml"
    if chapter_index_file.exists():
        chapter_index = load_yaml_list(chapter_index_file)
        total_chapters = len(chapter_index)

        # 统计已分析的章节数量
        chapters_dir = novel_dir / "chapters"
        if chapters_dir.exists():
            analyzed_count = len(list(chapters_dir.glob("*.yaml")))
        else:
            chapters_file = novel_dir / "chapters.yaml"
            if chapters_file.exists():
                chapters_data = load_yaml_list(chapters_file)
                analyzed_count = len(chapters_data)
            else:
                analyzed_count = 0

        analyzed = analyzed_count >= total_chapters and total_chapters > 0

    # 检查数据库同步
    database = probe_database_status(material_id)

    return {
        "exists": True,
        "ingested": (novel_dir / "chapter_index.yaml").exists(),
        "evaluation": _has_complete_evaluation(novel_dir),
        "analyzed": analyzed,
        "chapters_embedded": (novel_dir / "chapter_embeddings.npz").exists(),
        "outline": (novel_dir / "outline" / "_index.yaml").exists(),
        "outline_embedded": (novel_dir / "outline" / "outline_embeddings.npz").exists(),
        "worldbuilding": (novel_dir / "worldbuilding" / "_index.yaml").exists(),
        "worldbuilding_embedded": (novel_dir / "worldbuilding" / "wb_embeddings.npz").exists(),
        "characters": (novel_dir / "characters" / "_index.yaml").exists(),
        "characters_embedded": (novel_dir / "characters" / "character_embeddings.npz").exists(),
        "tags": (novel_dir / "tags.yaml").exists(),
        "insights": has_complete_insights(novel_dir),
        "refined": meta.get("refined_at") is not None,
        "synced": database.status == "synced",
        "database_status": database.status,
        "database_diagnostic": database.diagnostic,
        "meta_status": meta.get("status"),
        "name": meta.get("name", "未知"),
        "chapter_count": meta.get("chapter_count", 0),
    }


def print_pipeline_status(progress: dict) -> None:
    """打印进度表格。"""
    if not progress.get("exists"):
        console.print("[red]素材目录不存在[/red]")
        return

    # 基本信息
    console.print(f"\n[bold]{progress.get('name', '未知')}[/bold] ({progress.get('chapter_count', 0)} 章)")
    console.print(f"meta.yaml 状态: [cyan]{progress.get('meta_status', '未知')}[/cyan]")

    # 进度表格
    table = Table(title="流水线进度")
    table.add_column("阶段", style="cyan")
    table.add_column("状态", style="green")

    for name, key, _ in PIPELINE_STAGES:
        # evaluation 是可选阶段，显示不同标记
        if key == "evaluation":
            status = "✓ 完成" if progress.get(key) else "- 未运行（可选）"
        else:
            status = "✓ 完成" if progress.get(key) else "○ 未完成"
        table.add_row(name, status)

    console.print(table)

    # 向量状态表格
    embed_table = Table(title="向量状态")
    embed_table.add_column("类型", style="cyan")
    embed_table.add_column("状态", style="green")

    embed_keys = [
        ("章节", "chapters_embedded"),
        ("人物", "characters_embedded"),
        ("世界观", "worldbuilding_embedded"),
        ("大纲", "outline_embedded"),
    ]
    for name, key in embed_keys:
        status = "✓ 已生成" if progress.get(key) else "○ 未生成"
        embed_table.add_row(name, status)

    console.print(embed_table)


def get_next_pending_stage(
    progress: dict,
    include_insights: bool = True,
    include_navigation: bool = False,
) -> str | None:
    """获取下一个待执行的阶段名称。

    Returns:
        str | None: 阶段名称，如果全部完成则返回 None
    """
    if not progress.get("exists"):
        return None

    if not progress.get("ingested"):
        return "ingest"

    if include_navigation and not progress.get("evaluation"):
        return "evaluation"

    if not progress.get("analyzed"):
        return "analyze"

    # 从 PIPELINE_STAGES 获取骨架阶段顺序（保持定义顺序）
    skeleton_keys = ["outline", "worldbuilding", "characters", "tags"]
    skeleton_stages = [
        (key, key)
        for _, key, _ in PIPELINE_STAGES
        if key in skeleton_keys
    ]

    for name, key in skeleton_stages:
        if not progress.get(key):
            return name

    if include_insights and not progress.get("insights"):
        return "insights"

    if not progress.get("refined"):
        return "refine"

    if not progress.get("synced"):
        return "sync"

    return None


def calculate_total_stages(has_evaluation: bool, include_insights: bool = True) -> int:
    """计算流水线总阶段数（不含数据库同步）。

    Args:
        has_evaluation: 是否包含总体评估阶段（基于历史状态或本次参数）

    Returns:
        int: 总阶段数
    """
    return len(get_pipeline_stages(has_evaluation, include_insights=include_insights))


def calculate_current_stage(
    progress: dict,
    use_window_detected: bool,
    will_analyze: bool,
    include_insights: bool = True,
) -> int:
    """计算当前阶段编号（下一待执行阶段）。

    Args:
        progress: 进度检查结果字典
        use_window_detected: 是否检测到总体评估已完成
        will_analyze: 本次是否会执行章级分析

    Returns:
        int: 下一待执行阶段的编号（从 1 开始）
    """
    stages = get_pipeline_stages(use_window_detected, include_insights=include_insights)

    completed_count = 0
    for name, key in stages:
        if key == "analyzed":
            # 章级分析特殊处理：已完成且本次不重新执行才算完成
            if progress.get("analyzed") and not will_analyze:
                completed_count += 1
            else:
                break  # 未完成或需重新执行，停止计数
        elif key == "ingested":
            # 入库在 continue 模式下总是已完成
            completed_count += 1
        else:
            if progress.get(key):
                completed_count += 1
            else:
                break  # 未完成，停止计数

    return completed_count + 1  # 下一待执行阶段
