"""Pipeline 子命令：数据处理流水线。"""
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from novel_material.pipeline import (
    ingest_file,
    chapter_analyze,
    generate_outline,
    generate_worldbuilding,
    generate_characters,
    generate_tags,
    refine,
)
from novel_material.pipeline.progress import get_pipeline_progress, print_pipeline_status, get_next_pending_stage
from novel_material.storage.sync import sync_novel

app = typer.Typer(help="数据处理流水线")
console = Console()


@app.command("ingest")
def cmd_ingest(
    file_path: str = typer.Argument(..., help="小说文件路径"),
):
    """入库单本小说。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"正在入库: {file_path}", total=None)
        material_id = ingest_file(file_path)
        progress.update(task, completed=True)

    if material_id:
        console.print(f"[green]入库成功[/green] material_id: [cyan]{material_id}[/cyan]")
    else:
        console.print("[red]入库失败[/red]")


@app.command("analyze")
def cmd_analyze(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """章级分析：生成摘要、人物、标签。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"章级分析: {material_id}", total=None)
        chapter_analyze(material_id)
        progress.update(task, completed=True)

    console.print("[green]章级分析完成[/green]")


@app.command("outline")
def cmd_outline(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """生成大纲结构。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"生成大纲: {material_id}", total=None)
        generate_outline(material_id)
        progress.update(task, completed=True)

    console.print("[green]大纲生成完成[/green]")


@app.command("worldbuilding")
def cmd_worldbuilding(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """提取世界观设定。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"提取世界观: {material_id}", total=None)
        generate_worldbuilding(material_id)
        progress.update(task, completed=True)

    console.print("[green]世界观提取完成[/green]")


@app.command("characters")
def cmd_characters(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """提取人物体系。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"提取人物: {material_id}", total=None)
        generate_characters(material_id)
        progress.update(task, completed=True)

    console.print("[green]人物提取完成[/green]")


@app.command("tags")
def cmd_tags(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """生成多维标签。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"生成标签: {material_id}", total=None)
        generate_tags(material_id)
        progress.update(task, completed=True)

    console.print("[green]标签生成完成[/green]")


@app.command("refine")
def cmd_refine(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """精调大纲/人物/标签。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"精调数据: {material_id}", total=None)
        refine(material_id)
        progress.update(task, completed=True)

    console.print("[green]精调完成[/green]")


@app.command("full")
def cmd_full(
    file_path: str = typer.Argument(..., help="小说文件路径"),
):
    """完整流水线：入库 → 章级分析 → 骨架分析 → 精调。"""
    console.print("[cyan]开始完整流水线[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:

        # 阶段 1: 入库
        task1 = progress.add_task("阶段 1/7: 入库", total=1)
        material_id = ingest_file(file_path)
        if not material_id:
            console.print("[red]入库失败，终止流水线[/red]")
            raise typer.Exit(1)
        progress.update(task1, completed=1)

        # 阶段 2: 章级分析
        task2 = progress.add_task("阶段 2/7: 章级分析", total=1)
        chapter_analyze(material_id)
        progress.update(task2, completed=1)

        # 阶段 3: 大纲
        task3 = progress.add_task("阶段 3/7: 大纲生成", total=1)
        generate_outline(material_id)
        progress.update(task3, completed=1)

        # 阶段 4: 世界观
        task4 = progress.add_task("阶段 4/7: 世界观提取", total=1)
        generate_worldbuilding(material_id)
        progress.update(task4, completed=1)

        # 阶段 5: 人物
        task5 = progress.add_task("阶段 5/7: 人物提取", total=1)
        generate_characters(material_id)
        progress.update(task5, completed=1)

        # 阶段 6: 标签
        task6 = progress.add_task("阶段 6/7: 标签生成", total=1)
        generate_tags(material_id)
        progress.update(task6, completed=1)

        # 阶段 7: 精调
        task7 = progress.add_task("阶段 7/7: 数据精调", total=1)
        refine(material_id)
        progress.update(task7, completed=1)

    # 结果表格
    table = Table(title="流水线完成")
    table.add_column("阶段", style="cyan")
    table.add_column("状态", style="green")
    table.add_row("入库", "✓")
    table.add_row("章级分析", "✓")
    table.add_row("大纲", "✓")
    table.add_row("世界观", "✓")
    table.add_row("人物", "✓")
    table.add_row("标签", "✓")
    table.add_row("精调", "✓")
    console.print(table)
    console.print(f"[green]material_id:[/green] [cyan]{material_id}[/cyan]")


@app.command("status")
def cmd_status(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """查看流水线进度。"""
    progress = get_pipeline_progress(material_id)
    print_pipeline_status(progress)

    next_stage = get_next_pending_stage(progress)
    if next_stage:
        console.print(f"\n[yellow]下一步: nm pipeline continue {material_id}[/yellow]")
    else:
        console.print("\n[green]流水线已完成[/green]")


@app.command("continue")
def cmd_continue(
    material_id: str = typer.Argument(..., help="素材 ID"),
    skip_sync: bool = typer.Option(False, "--skip-sync", help="跳过数据库同步"),
):
    """自动从断点继续流水线。

    根据进度检查结果，自动执行未完成的阶段：
    - 章级分析（有断点续传）
    - 骨架分析（大纲、世界观、人物、标签）
    - 精调
    - 数据库同步
    """
    progress = get_pipeline_progress(material_id)
    print_pipeline_status(progress)

    if not progress.get("exists"):
        console.print("[red]素材目录不存在，请先执行 nm pipeline ingest[/red]")
        raise typer.Exit(1)

    if not progress.get("ingested"):
        console.print("[red]素材未入库，请先执行 nm pipeline ingest[/red]")
        raise typer.Exit(1)

    # 显示续传信息
    next_stage = get_next_pending_stage(progress)
    if not next_stage:
        console.print("\n[green]流水线已完成，无需续传[/green]")
        if not skip_sync and not progress.get("synced"):
            console.print("[yellow]提示：数据库未同步，可执行 nm storage sync[/yellow]")
        return

    console.print(f"\n[cyan]从 {next_stage} 阶段继续[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress_bar:

        # 阶段 1: 章级分析
        if not progress.get("analyzed"):
            task1 = progress_bar.add_task("阶段 1: 章级分析", total=1)
            chapter_analyze(material_id)
            progress_bar.update(task1, completed=1)

        # 阶段 2-5: 骨架分析
        skeleton_stages = [
            ("大纲", generate_outline, "outline"),
            ("世界观", generate_worldbuilding, "worldbuilding"),
            ("人物", generate_characters, "characters"),
            ("标签", generate_tags, "tags"),
        ]

        task_num = 2
        for name, func, key in skeleton_stages:
            if not progress.get(key):
                task = progress_bar.add_task(f"阶段 {task_num}: {name}", total=1)
                func(material_id)
                progress_bar.update(task, completed=1)
            task_num += 1

        # 阶段 6: 精调
        if not progress.get("refined"):
            task6 = progress_bar.add_task("阶段 6: 精调", total=1)
            refine(material_id)
            progress_bar.update(task6, completed=1)

        # 阶段 7: 数据库同步
        sync_failed = False
        if not skip_sync and not progress.get("synced"):
            task7 = progress_bar.add_task("阶段 7: 同步数据库", total=1)
            try:
                sync_novel(material_id)
                progress_bar.update(task7, completed=1)
            except Exception as e:
                sync_failed = True
                console.print(f"[red]数据库同步失败: {e}[/red]")
                console.print("[yellow]可手动执行 nm storage sync 重试[/yellow]")

    # 完成表格
    table = Table(title="流水线完成")
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

    final_progress = get_pipeline_progress(material_id)
    for name, key in stages:
        if key == "synced" and skip_sync:
            status = "○ 已跳过"
        elif key == "synced" and sync_failed:
            status = "✗ 失败"
        else:
            status = "✓ 完成" if final_progress.get(key) else "○ 未完成"
        table.add_row(name, status)

    console.print(table)
    console.print(f"[green]material_id:[/green] [cyan]{material_id}[/cyan]")