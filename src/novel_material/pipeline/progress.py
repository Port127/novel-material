"""流水线进度检查：检查各阶段完成情况，支持断点续传。"""
import os
import yaml
import psycopg2
from dotenv import load_dotenv
from pathlib import Path
from rich.console import Console
from rich.table import Table

from novel_material.infra.config import NOVELS_DIR

load_dotenv()
console = Console()


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
        meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}

    # 检查数据库同步
    synced = False
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM novels WHERE material_id = %s", [material_id])
            synced = cur.fetchone() is not None
        conn.close()
    except Exception:
        synced = False

    return {
        "exists": True,
        "ingested": (novel_dir / "chapter_index.yaml").exists(),
        "analyzed": (novel_dir / "chapters.yaml").exists(),
        "outline": (novel_dir / "outline" / "_index.yaml").exists(),
        "worldbuilding": (novel_dir / "worldbuilding" / "_index.yaml").exists(),
        "characters": (novel_dir / "characters" / "_index.yaml").exists(),
        "tags": (novel_dir / "tags.yaml").exists(),
        "refined": meta.get("refined_at") is not None,
        "synced": synced,
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

    stages = [
        ("入库", "ingested"),
        ("章级分析", "analyzed"),
        ("大纲", "outline"),
        ("世界观", "worldbuilding"),
        ("人物", "characters"),
        ("标签", "tags"),
        ("精调", "refined"),
        ("数据库同步", "synced"),
    ]

    for name, key in stages:
        status = "✓ 完成" if progress.get(key) else "○ 未完成"
        table.add_row(name, status)

    console.print(table)


def get_next_pending_stage(progress: dict) -> str | None:
    """获取下一个待执行的阶段名称。

    Returns:
        str | None: 阶段名称，如果全部完成则返回 None
    """
    if not progress.get("exists"):
        return None

    if not progress.get("ingested"):
        return "ingest"

    if not progress.get("analyzed"):
        return "analyze"

    skeleton_stages = [
        ("outline", "outline"),
        ("worldbuilding", "worldbuilding"),
        ("characters", "characters"),
        ("tags", "tags"),
    ]

    for name, key in skeleton_stages:
        if not progress.get(key):
            return name

    if not progress.get("refined"):
        return "refine"

    if not progress.get("synced"):
        return "sync"

    return None