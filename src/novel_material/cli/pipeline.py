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
    table.add_row("入库", "✓")
    table.add_row("大纲", "✓")
    table.add_row("世界观", "✓")
    table.add_row("人物", "✓")
    table.add_row("标签", "✓")
    table.add_row("精调", "✓")
    console.print(table)
    console.print(f"[green]material_id:[/green] [cyan]{material_id}[/cyan]")