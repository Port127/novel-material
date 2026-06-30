"""Pipeline 子命令：数据处理流水线。"""
import sys
from types import SimpleNamespace

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.logging_config import ensure_log_dir
from novel_material.infra.yaml_io import load_yaml_list
from novel_material.infra.progress import silent_console, get_pipeline_logger
from novel_material.pipeline import (
    ingest_file,
    chapter_analyze,
    generate_outline,
    generate_worldbuilding,
    generate_characters,
    generate_tags,
    refine,
    run_evaluation,
)
from novel_material.pipeline.progress import (
    get_pipeline_progress,
    print_pipeline_status,
    get_next_pending_stage,
    inspect_pipeline_state,
    next_pending_stage,
    calculate_total_stages,
    calculate_current_stage,
    get_pipeline_stages,
    EVALUATION_STAGES,
    CHARACTERS_STAGES,
    WORLDBUILDING_STAGES,
)
from novel_material.pipeline.insights import generate_chapter_insights
from novel_material.pipeline.runtime_modes import get_runtime_mode
from novel_material.pipeline.state import (
    ConcurrentRunError,
    PipelineStateCorruptError,
    PipelineStateError,
    PipelineStateStore,
)
from novel_material.pipeline.stages import (
    run_characters_stage,
    run_ingest_stage,
    run_outline_stage,
    run_profile_stage,
    run_refine_stage,
    run_tags_stage,
    run_worldbuilding_stage,
)
from novel_material.storage.sync import sync_novel
from novel_material.cli.pipeline_common import (
    PipelineRuntime,
    run_continue_pipeline,
    run_full_pipeline,
)
from novel_material.reporting.builder import ReportBuildError, build_run_report
from novel_material.reporting.writer import (
    ReportConflictError,
    ReportHistoryError,
    ReportWriter,
)
from novel_material.run_logging.reader import RunLogReadError, read_run_events
from novel_material.terminal.modes import resolve_mode
from novel_material.terminal.reporter import TerminalReporter

app = typer.Typer(help="数据处理流水线")
console = Console()
logger = get_pipeline_logger()
_PIPELINE_SEPARATOR = "=" * 60


@app.command("ingest")
def cmd_ingest(
    file_path: str = typer.Argument(..., help="小说文件路径"),
):
    """入库单本小说。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"正在入库: {file_path}", total=1)
        result = run_ingest_stage(file_path)
        progress.update(task, completed=1)

    if result.status.value == "success":
        material_id = result.outputs["material_id"]
        console.print(f"[green]入库成功[/green] material_id: [cyan]{material_id}[/cyan]")
    else:
        typer.echo("入库失败", err=True)
        raise typer.Exit(1)


@app.command("analyze")
def cmd_analyze(
    material_id: str = typer.Argument(..., help="素材 ID"),
    start: int = typer.Option(None, "--start", "-s", help="起始章节号"),
    end: int = typer.Option(None, "--end", "-e", help="结束章节号（不指定则到结尾）"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称（如 deepseek）"),
    use_window: bool = typer.Option(False, "--window", "-w", help="启用滑动窗口模式"),
    skip_embedding: bool = typer.Option(False, "--skip-embedding", help="跳过章节向量化"),
):
    """章级分析：生成摘要、人物、标签（可选章节向量化）。

    滑动窗口模式（--window）：
    - 为每章提供前章摘要；若存在 evaluation.yaml，会一并使用前置导航作为上下文
    - 输出新增字段：tension_change、emotion_transition、plot_progress
    """
    # 验证参数
    if start is not None and start < 1:
        console.print("[red]起始章节号必须 >= 1[/red]")
        raise typer.Exit(1)
    if start is not None and end is not None and end < start:
        console.print("[red]结束章节号必须 >= 起始章节号[/red]")
        raise typer.Exit(1)

    novel_dir = NOVELS_DIR / material_id
    chapter_index = load_yaml_list(novel_dir / "chapter_index.yaml")
    total_chapters = len(chapter_index)

    # 验证范围不超出章节总数
    if start is not None and start > total_chapters:
        console.print(f"[red]起始章节号 {start} 超出总章数 {total_chapters}[/red]")
        raise typer.Exit(1)
    if end is not None and end > total_chapters:
        console.print(f"[red]结束章节号 {end} 超出总章数 {total_chapters}[/red]")
        raise typer.Exit(1)

    # 计算范围内章节数
    chapters_in_range = [
        ch for ch in chapter_index
        if (start is None or ch["chapter"] >= start)
        and (end is None or ch["chapter"] <= end)
    ]
    range_total = len(chapters_in_range)

    # 显示范围信息
    range_desc = ""
    if start is not None or end is not None:
        range_start = start or 1
        range_end = end or total_chapters
        range_desc = f" (第 {range_start}-{range_end} 章)"
    window_desc = " [滑动窗口]" if use_window else ""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"章级分析: {material_id}{range_desc}{window_desc}", total=range_total)

        def update_progress(done: int, total: int, desc: str):
            progress.update(task, completed=done, description=f"章级分析: {desc}")

        with silent_console():
            chapter_analyze(
                material_id,
                start_ch=start,
                end_ch=end,
                progress_callback=update_progress,
                provider=provider,
                use_window=use_window,
                skip_embedding=skip_embedding,
            )

    console.print("[green]章级分析完成[/green]")

    # 如果指定了范围，警告后续阶段可能基于不完整数据
    if start is not None or end is not None:
        console.print("[yellow]警告：仅分析了部分章节，后续阶段（大纲、世界观等）将基于不完整的章级数据生成[/yellow]")
        console.print("[yellow]建议：分析全书后再执行后续阶段，或使用 nm pipeline continue --skip-sync 完成后续[/yellow]")


@app.command("insights")
def cmd_insights(
    material_id: str = typer.Argument(..., help="素材 ID"),
    start: int = typer.Option(None, "--start", "-s", help="起始章节号"),
    end: int = typer.Option(None, "--end", "-e", help="结束章节号"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
    profile: list[str] = typer.Option(None, "--profile", help="显式指定 profile，可重复传入"),
):
    """题材感知深度分析：生成 chapter_insights/{chapter}.yaml。"""
    novel_dir = NOVELS_DIR / material_id
    chapter_index = load_yaml_list(novel_dir / "chapter_index.yaml")
    total_chapters = len(chapter_index)

    if start is not None and start < 1:
        console.print("[red]起始章节号必须 >= 1[/red]")
        raise typer.Exit(1)
    if start is not None and end is not None and end < start:
        console.print("[red]结束章节号必须 >= 起始章节号[/red]")
        raise typer.Exit(1)
    if start is not None and start > total_chapters:
        console.print(f"[red]起始章节号 {start} 超出总章数 {total_chapters}[/red]")
        raise typer.Exit(1)
    if end is not None and end > total_chapters:
        console.print(f"[red]结束章节号 {end} 超出总章数 {total_chapters}[/red]")
        raise typer.Exit(1)

    chapters_in_range = [
        ch for ch in chapter_index
        if (start is None or ch["chapter"] >= start)
        and (end is None or ch["chapter"] <= end)
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress_bar:
        task = progress_bar.add_task(f"深度分析: {material_id}", total=len(chapters_in_range))

        def update_progress(done: int, total: int, desc: str):
            progress_bar.update(task, total=total, completed=done, description=f"深度分析: {desc}")

        with silent_console():
            success = generate_chapter_insights(
                material_id,
                start_ch=start,
                end_ch=end,
                provider=provider,
                explicit_profiles=profile,
                progress_callback=update_progress,
            )

    if not success:
        console.print("[red]深度分析失败[/red]")
        raise typer.Exit(1)
    console.print("[green]深度分析完成[/green]")


@app.command("evaluate")
def cmd_evaluate(
    material_id: str = typer.Argument(..., help="素材 ID"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
):
    """总体评估：对小说做全局评估，生成类型、主线概要、阶段概要。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"总体评估: {material_id}", total=EVALUATION_STAGES)

        def update_progress(done: int, total: int, desc: str):
            progress.update(task, completed=done, description=f"总体评估: {desc}")

        with silent_console():
            success = run_evaluation(material_id, provider=provider, progress_callback=update_progress, silent=True)

    if success:
        console.print("[green]总体评估完成[/green]")
    else:
        console.print("[red]总体评估失败[/red]")
        raise typer.Exit(1)


@app.command("outline")
def cmd_outline(
    material_id: str = typer.Argument(..., help="素材 ID"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
):
    """生成大纲结构。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"生成大纲: {material_id}", total=None)

        def update_progress(done: int, total: int, desc: str):
            if total > 0:
                progress.update(task, total=total, completed=done, description=f"生成大纲: {desc}")
            else:
                progress.update(task, description=f"生成大纲: {desc}")

        with silent_console():
            result = run_outline_stage(
                material_id,
                progress_callback=update_progress,
                provider=provider,
            )

    if result.status.value == "failed":
        typer.echo("大纲生成失败", err=True)
        raise typer.Exit(1)
    console.print("[green]大纲生成完成[/green]")


@app.command("worldbuilding")
def cmd_worldbuilding(
    material_id: str = typer.Argument(..., help="素材 ID"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
):
    """提取世界观设定。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"提取世界观: {material_id}", total=WORLDBUILDING_STAGES)
        result = run_worldbuilding_stage(material_id, provider=provider)
        progress.update(task, completed=1)

    if result.status.value == "failed":
        typer.echo("世界观提取失败", err=True)
        raise typer.Exit(1)
    console.print("[green]世界观提取完成[/green]")


@app.command("characters")
def cmd_characters(
    material_id: str = typer.Argument(..., help="素材 ID"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
    repair_character: list[str] | None = typer.Option(
        None,
        "--repair-character",
        help="只重建指定人物，可重复",
    ),
):
    """提取人物体系。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"提取人物: {material_id}", total=CHARACTERS_STAGES)  # 核心/配角/次要

        def update_chars_progress(done: int, total: int, desc: str):
            progress.update(task, completed=done, description=f"提取人物: {desc}")

        with silent_console():
            result = run_characters_stage(
                material_id,
                progress_callback=update_chars_progress,
                provider=provider,
                repair_characters=tuple(repair_character or ()),
            )

    if result.status.value == "failed":
        typer.echo("人物提取失败", err=True)
        raise typer.Exit(1)
    console.print("[green]人物提取完成[/green]")


@app.command("tags")
def cmd_tags(
    material_id: str = typer.Argument(..., help="素材 ID"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
):
    """生成多维标签。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"生成标签: {material_id}", total=1)
        result = run_tags_stage(material_id, provider=provider)
        progress.update(task, completed=1)

    if result.status.value == "failed":
        typer.echo("标签生成失败", err=True)
        raise typer.Exit(1)
    console.print("[green]标签生成完成[/green]")


@app.command("refine")
def cmd_refine(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """精调大纲/人物/标签。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"精调 + 向量化: {material_id}", total=2)
        with silent_console():
            result = run_refine_stage(material_id)
            if result.status.value == "failed":
                progress.update(task, completed=2)
                typer.echo("精调失败", err=True)
                raise typer.Exit(1)
        progress.update(task, completed=2)

    console.print("[green]精调完成[/green]")


@app.command("profile")
def cmd_profile(
    material_id: str = typer.Argument(..., help="素材 ID"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
):
    """生成作品画像 work_profile.yaml。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"生成作品画像: {material_id}", total=1)
        result = run_profile_stage(material_id, provider=provider)
        progress.update(task, completed=1)

    if result.status.value == "failed":
        typer.echo("作品画像生成失败", err=True)
        raise typer.Exit(1)
    console.print("[green]作品画像生成完成[/green]")


def _legacy_cmd_full(
    file_path: str = typer.Argument(..., help="小说文件路径"),
    start: int = typer.Option(None, "--start", "-s", help="起始章节号"),
    end: int = typer.Option(None, "--end", "-e", help="结束章节号（不指定则到结尾）"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
    use_window: bool = typer.Option(False, "--window", "-w", help="启用滑动窗口模式"),
    mode: str = typer.Option("standard", "--mode", help="运行模式：fast / standard / deep"),
    skip_sync: bool = typer.Option(False, "--skip-sync", help="跳过数据库同步"),
    skip_embedding: bool = typer.Option(False, "--skip-embedding", help="跳过章节向量化"),
):
    """完整流水线：入库 → 章级分析 → 骨架分析 → 精调 → 数据库同步。

    滑动窗口模式（--window）：
    - 前置导航由运行模式或 --navigation 控制
    - 为每章提供前章摘要；若存在 evaluation.yaml，会一并使用前置导航作为上下文
    - 输出新增字段：tension_change、emotion_transition、plot_progress
    """
    # 验证参数
    if start is not None and start < 1:
        console.print("[red]起始章节号必须 >= 1[/red]")
        raise typer.Exit(1)
    if start is not None and end is not None and end < start:
        console.print("[red]结束章节号必须 >= 起始章节号[/red]")
        raise typer.Exit(1)

    # 显示范围信息
    range_desc = ""
    if start is not None or end is not None:
        range_start = start or 1
        range_end_text = end or "末"
        range_desc = f" (第 {range_start}-{range_end_text} 章)"
    window_desc = " [滑动窗口]" if use_window else ""
    runtime_mode = get_runtime_mode(mode)
    total_stages = calculate_total_stages(use_window, include_insights=runtime_mode.include_core_insights)

    console.print(f"[cyan]开始完整流水线{range_desc}{window_desc}[/cyan]")
    logger.info(_PIPELINE_SEPARATOR)

    sync_failed = False  # 数据库同步状态（Progress 块外）

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:

        # 阶段 1: 入库
        console.print(f"[cyan]阶段 1/{total_stages}: 入库...[/cyan]")
        task1 = progress.add_task("入库处理", total=1)
        with silent_console():
            material_id = ingest_file(file_path)
        if not material_id:
            console.print("[red]入库失败，终止流水线[/red]")
            raise typer.Exit(1)
        progress.update(task1, completed=1)
        console.print(f"[green]入库完成: {material_id}[/green]")
        progress.remove_task(task1)

        # 阶段 2: 总体评估（仅滑动窗口模式）
        if use_window:
            console.print(f"[cyan]阶段 2/{total_stages}: 总体评估...[/cyan]")
            task_eval = progress.add_task("总体评估", total=5)

            def update_eval_progress(done: int, total: int, desc: str):
                progress.update(task_eval, completed=done, description=f"总体评估: {desc}")

            with silent_console():
                success = run_evaluation(material_id, provider=provider, progress_callback=update_eval_progress, silent=True)
            if not success:
                console.print("[red]总体评估失败，终止流水线[/red]")
                raise typer.Exit(1)
            progress.remove_task(task_eval)

        # 阶段 N: 章级分析（细粒度进度）
        analyze_stage = 2 if not use_window else 3
        novel_dir = NOVELS_DIR / material_id
        chapter_index = load_yaml_list(novel_dir / "chapter_index.yaml")
        total_chapters = len(chapter_index)

        # 验证范围不超出章节总数（入库后才知道总章数）
        if start is not None and start > total_chapters:
            console.print(f"[red]起始章节号 {start} 超出总章数 {total_chapters}[/red]")
            raise typer.Exit(1)
        if end is not None and end > total_chapters:
            console.print(f"[red]结束章节号 {end} 超出总章数 {total_chapters}[/red]")
            raise typer.Exit(1)

        # 计算范围内章节数
        chapters_in_range = [
            ch for ch in chapter_index
            if (start is None or ch["chapter"] >= start)
            and (end is None or ch["chapter"] <= end)
        ]
        range_total = len(chapters_in_range)

        task2 = progress.add_task(f"阶段 {analyze_stage}/{total_stages}: 章级分析", total=range_total)

        def update_progress(done: int, total: int, desc: str):
            progress.update(task2, completed=done, description=f"阶段 {analyze_stage}/{total_stages}: {desc}")

        with silent_console():
            chapter_analyze(
                material_id,
                start_ch=start,
                end_ch=end,
                progress_callback=update_progress,
                provider=provider,
                use_window=use_window,
                skip_embedding=skip_embedding,
            )
        progress.remove_task(task2)

        # 阶段 N+1: 大纲（不确定进度，序列数动态计算）
        outline_stage = analyze_stage + 1
        task3 = progress.add_task(f"阶段 {outline_stage}/{total_stages}: 大纲生成", total=None)

        def update_outline_progress(done: int, total: int, desc: str):
            if total > 0:
                progress.update(task3, total=total, completed=done, description=f"阶段 {outline_stage}/{total_stages}: {desc}")
            else:
                progress.update(task3, description=f"阶段 {outline_stage}/{total_stages}: {desc}")

        with silent_console():
            generate_outline(material_id, progress_callback=update_outline_progress, provider=provider)
        progress.remove_task(task3)

        # 阶段 N+2: 世界观
        world_stage = outline_stage + 1
        task4 = progress.add_task(f"阶段 {world_stage}/{total_stages}: 世界观提取", total=1)
        with silent_console():
            generate_worldbuilding(material_id, provider=provider)
        progress.update(task4, completed=1)
        progress.remove_task(task4)

        # 阶段 N+3: 人物
        char_stage = world_stage + 1
        task5 = progress.add_task(f"阶段 {char_stage}/{total_stages}: 人物提取", total=3)  # 核心/配角/次要

        def update_chars_progress_full(done: int, total: int, desc: str):
            progress.update(task5, completed=done, description=f"阶段 {char_stage}/{total_stages}: {desc}")

        with silent_console():
            generate_characters(material_id, progress_callback=update_chars_progress_full, provider=provider)
        progress.remove_task(task5)

        # 阶段 N+4: 标签
        tags_stage = char_stage + 1
        task6 = progress.add_task(f"阶段 {tags_stage}/{total_stages}: 标签生成", total=1)
        with silent_console():
            generate_tags(material_id, provider=provider)
        progress.update(task6, completed=1)
        progress.remove_task(task6)

        # 阶段 N+5: 深度分析（standard/deep）
        refine_stage = tags_stage + 1
        if runtime_mode.include_core_insights:
            insights_stage = tags_stage + 1
            task_insights = progress.add_task(
                f"阶段 {insights_stage}/{total_stages}: 深度分析",
                total=total_chapters,
            )

            def update_insights_progress(done: int, total: int, desc: str):
                progress.update(
                    task_insights,
                    total=total,
                    completed=done,
                    description=f"阶段 {insights_stage}/{total_stages}: {desc}",
                )

            with silent_console():
                generate_chapter_insights(
                    material_id,
                    provider=provider,
                    progress_callback=update_insights_progress,
                )
            progress.remove_task(task_insights)
            refine_stage = insights_stage + 1

        # 阶段 N+6: 精调
        task7 = progress.add_task(f"阶段 {refine_stage}/{total_stages}: 精调 + 向量化", total=2)
        with silent_console():
            if not refine(material_id):
                console.print("[red]精调失败，终止流水线[/red]")
                raise typer.Exit(1)
        progress.update(task7, completed=2)
        progress.remove_task(task7)

        # 数据库同步（不计入总阶段数）
        if not skip_sync:
            task_sync = progress.add_task("同步数据库", total=1)
            with silent_console():
                success = sync_novel(material_id, provider=provider, use_window=use_window)
                if not success:
                    sync_failed = True
                    console.print("[red]数据库同步失败[/red]")
                    console.print("[yellow]可手动执行 nm storage sync 重试[/yellow]")
            if not sync_failed:
                progress.update(task_sync, completed=1)
                progress.remove_task(task_sync)

    # 结果表格
    # 如果指定了范围，警告后续阶段基于不完整数据
    if start is not None or end is not None:
        console.print("[yellow]警告：仅分析了部分章节，大纲/世界观/人物等基于不完整的章级数据生成[/yellow]")

    table = Table(title="流水线完成")
    table.add_column("阶段", style="cyan")
    table.add_column("状态", style="green")

    # 数据库同步不计入总阶段数，单独添加
    stages = get_pipeline_stages(use_window, include_insights=runtime_mode.include_core_insights)
    stages.append(("数据库同步", "synced"))

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


@app.command("status")
def cmd_status(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """查看流水线进度。"""
    try:
        inspection = inspect_pipeline_state(material_id)
    except PipelineStateError as exc:
        _raise_pipeline_state_cli_error(exc)
    if not inspection.exists:
        typer.echo("素材目录不存在", err=True)
        raise typer.Exit(1)

    table = Table(title="流水线状态")
    table.add_column("阶段", style="cyan")
    table.add_column("状态")
    labels = {
        "success": "✓ 成功",
        "degraded": "△ 降级",
        "failed": "✗ 失败",
        "interrupted": "! 已中断",
        "running": "… 运行中",
        "pending": "○ 待处理",
    }
    for name, stage in inspection.stages.items():
        table.add_row(name, labels.get(stage.status.value, stage.status.value))
    console.print(table)

    next_stage = next_pending_stage(inspection)
    if next_stage:
        console.print(f"\n[yellow]下一步: nm pipeline continue {material_id}[/yellow]")
    else:
        console.print("\n[green]流水线已完成[/green]")


def _legacy_cmd_continue(
    material_id: str = typer.Argument(..., help="素材 ID"),
    skip_sync: bool = typer.Option(False, "--skip-sync", help="跳过数据库同步"),
    start: int = typer.Option(None, "--start", "-s", help="起始章节号"),
    end: int = typer.Option(None, "--end", "-e", help="结束章节号（不指定则到结尾）"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
    use_window: bool = typer.Option(False, "--window", "-w", help="启用滑动窗口模式"),
    mode: str = typer.Option("standard", "--mode", help="运行模式：fast / standard / deep"),
    skip_embedding: bool = typer.Option(False, "--skip-embedding", help="跳过章节向量化"),
):
    """自动从断点继续流水线。

    根据进度检查结果，自动执行未完成的阶段：
    - 章级分析（有断点续传）
    - 骨架分析（大纲、世界观、人物、标签）
    - 精调
    - 数据库同步

    滑动窗口模式（--window）：
    - 为每章提供前章摘要；若存在 evaluation.yaml，会一并使用前置导航作为上下文
    """
    # 验证参数
    if start is not None and start < 1:
        console.print("[red]起始章节号必须 >= 1[/red]")
        raise typer.Exit(1)
    if start is not None and end is not None and end < start:
        console.print("[red]结束章节号必须 >= 起始章节号[/red]")
        raise typer.Exit(1)

    runtime_mode = get_runtime_mode(mode)
    progress = get_pipeline_progress(material_id)
    print_pipeline_status(progress)

    if not progress.get("exists"):
        console.print("[red]素材目录不存在，请先执行 nm pipeline ingest[/red]")
        raise typer.Exit(1)

    if not progress.get("ingested"):
        console.print("[red]素材未入库，请先执行 nm pipeline ingest[/red]")
        raise typer.Exit(1)

    # 显示续传信息
    next_stage = get_next_pending_stage(progress, include_insights=runtime_mode.include_core_insights)
    # 如果指定了范围，即使流水线已完成，也要执行（允许重新分析指定范围）
    if not next_stage and start is None and end is None:
        console.print("\n[green]流水线已完成，无需续传[/green]")
        if not skip_sync and not progress.get("synced"):
            console.print("[yellow]提示：数据库未同步，可执行 nm storage sync[/yellow]")
        return

    # 加载章节信息（用于范围验证和显示）
    novel_dir = NOVELS_DIR / material_id
    chapter_index = load_yaml_list(novel_dir / "chapter_index.yaml")
    total_chapters = len(chapter_index)

    # 验证参数范围
    if start is not None and start > total_chapters:
        console.print(f"[red]起始章节号 {start} 超出总章数 {total_chapters}[/red]")
        raise typer.Exit(1)
    if end is not None and end > total_chapters:
        console.print(f"[red]结束章节号 {end} 超出总章数 {total_chapters}[/red]")
        raise typer.Exit(1)

    # 计算总阶段数和当前阶段编号（动态）
    use_window_detected = progress.get("evaluation")
    total_stages = calculate_total_stages(use_window_detected, include_insights=runtime_mode.include_core_insights)

    # 预计算：本次是否会执行章级分析
    # 条件：章级分析未完成，或用户指定了范围（即使已完成也要重新分析）
    will_analyze = not progress.get("analyzed") or start is not None or end is not None

    # 计算当前阶段编号
    current_stage = calculate_current_stage(
        progress,
        use_window_detected,
        will_analyze,
        include_insights=runtime_mode.include_core_insights,
    )

    # 显示范围信息
    range_desc = ""
    if start is not None or end is not None:
        range_start = start or 1
        range_end_text = end or total_chapters
        range_desc = f" (第 {range_start}-{range_end_text} 章)"

    next_stage_display = next_stage or "章级分析"
    console.print(f"\n[cyan]从 {next_stage_display} 阶段继续{range_desc}[/cyan]")
    logger.info(_PIPELINE_SEPARATOR)

    # 计算范围内章节数
    chapters_in_range = [
        ch for ch in chapter_index
        if (start is None or ch["chapter"] >= start)
        and (end is None or ch["chapter"] <= end)
    ]
    range_total = len(chapters_in_range)

    sync_failed = False  # 数据库同步状态（Progress 块外）

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress_bar:

        # 章级分析（细粒度进度）
        # 如果指定了范围，即使进度检查认为已完成，也要进入分析阶段（让内部判断是否需要分析）
        if will_analyze:
            console.print(f"[cyan]阶段 {current_stage}/{total_stages}: 章级分析...[/cyan]")
            task1 = progress_bar.add_task(f"阶段 {current_stage}/{total_stages}: 章级分析", total=range_total)

            def update_progress(done: int, total: int, desc: str):
                progress_bar.update(task1, completed=done, description=f"阶段 {current_stage}/{total_stages}: {desc}")

            with silent_console():
                chapter_analyze(
                    material_id,
                    start_ch=start,
                    end_ch=end,
                    progress_callback=update_progress,
                    provider=provider,
                    use_window=use_window,
                    skip_embedding=skip_embedding,
                )
            progress_bar.remove_task(task1)
            current_stage += 1

        # 大纲（不确定进度）
        if not progress.get("outline"):
            # 警告：如果指定了范围，后续阶段基于不完整数据
            if start is not None or end is not None:
                console.print("[yellow]警告：仅分析了部分章节，大纲/世界观/人物等将基于不完整的章级数据生成[/yellow]")

            console.print(f"[cyan]阶段 {current_stage}/{total_stages}: 大纲生成...[/cyan]")
            task2 = progress_bar.add_task(f"阶段 {current_stage}/{total_stages}: 大纲", total=None)

            def update_outline_progress(done: int, total: int, desc: str):
                if total > 0:
                    progress_bar.update(task2, total=total, completed=done, description=f"阶段 {current_stage}/{total_stages}: {desc}")
                else:
                    progress_bar.update(task2, description=f"阶段 {current_stage}/{total_stages}: {desc}")

            with silent_console():
                generate_outline(material_id, progress_callback=update_outline_progress, provider=provider)
            progress_bar.remove_task(task2)
            current_stage += 1

        # 世界观
        if not progress.get("worldbuilding"):
            console.print(f"[cyan]阶段 {current_stage}/{total_stages}: 世界观提取...[/cyan]")
            task = progress_bar.add_task(f"阶段 {current_stage}/{total_stages}: 世界观提取", total=1)
            with silent_console():
                generate_worldbuilding(material_id, provider=provider)
            progress_bar.update(task, completed=1)
            progress_bar.remove_task(task)
            current_stage += 1

        # 人物（细粒度进度）
        if not progress.get("characters"):
            console.print(f"[cyan]阶段 {current_stage}/{total_stages}: 人物提取...[/cyan]")
            task = progress_bar.add_task(f"阶段 {current_stage}/{total_stages}: 人物提取", total=3)  # 核心/配角/次要

            def update_chars_progress_continue(done: int, total: int, desc: str):
                progress_bar.update(task, completed=done, description=f"阶段 {current_stage}/{total_stages}: {desc}")

            with silent_console():
                generate_characters(material_id, progress_callback=update_chars_progress_continue, provider=provider)
            progress_bar.remove_task(task)
            current_stage += 1

        # 标签
        if not progress.get("tags"):
            console.print(f"[cyan]阶段 {current_stage}/{total_stages}: 标签生成...[/cyan]")
            task = progress_bar.add_task(f"阶段 {current_stage}/{total_stages}: 标签", total=1)
            with silent_console():
                generate_tags(material_id, provider=provider)
            progress_bar.update(task, completed=1)
            progress_bar.remove_task(task)
            current_stage += 1

        # 深度分析
        if runtime_mode.include_core_insights and not progress.get("insights"):
            console.print(f"[cyan]阶段 {current_stage}/{total_stages}: 深度分析...[/cyan]")
            task = progress_bar.add_task(f"阶段 {current_stage}/{total_stages}: 深度分析", total=total_chapters)

            def update_insights_progress_continue(done: int, total: int, desc: str):
                progress_bar.update(
                    task,
                    total=total,
                    completed=done,
                    description=f"阶段 {current_stage}/{total_stages}: {desc}",
                )

            with silent_console():
                generate_chapter_insights(
                    material_id,
                    provider=provider,
                    progress_callback=update_insights_progress_continue,
                )
            progress_bar.remove_task(task)
            current_stage += 1

        # 精调
        if not progress.get("refined"):
            console.print(f"[cyan]阶段 {current_stage}/{total_stages}: 数据精调...[/cyan]")
            task6 = progress_bar.add_task(f"阶段 {current_stage}/{total_stages}: 精调 + 向量化", total=2)
            with silent_console():
                if not refine(material_id):
                    console.print("[red]精调失败[/red]")
                    raise typer.Exit(1)
            progress_bar.update(task6, completed=2)
            progress_bar.remove_task(task6)
            current_stage += 1

        # 数据库同步（不计入总阶段数）
        if not skip_sync and not progress.get("synced"):
            task7 = progress_bar.add_task(f"同步数据库", total=1)
            with silent_console():
                success = sync_novel(material_id, provider=provider, use_window=use_window)
                if not success:
                    sync_failed = True
                    console.print("[red]数据库同步失败[/red]")
                    console.print("[yellow]可手动执行 nm storage sync 重试[/yellow]")
            if not sync_failed:
                progress_bar.update(task7, completed=1)
                progress_bar.remove_task(task7)

    # 完成表格
    # 如果指定了范围且后续阶段已存在，警告数据不一致
    if (start is not None or end is not None) and progress.get("outline"):
        console.print("[yellow]警告：指定范围分析后，大纲等后续阶段未重新生成，数据可能不一致[/yellow]")
        console.print("[yellow]建议：如需重新生成，可手动删除 outline/ 目录后重新执行[/yellow]")

    table = Table(title="流水线完成")
    table.add_column("阶段", style="cyan")
    table.add_column("状态", style="green")

    stages = get_pipeline_stages(use_window_detected, include_insights=runtime_mode.include_core_insights)
    # 数据库同步不计入总阶段数，单独添加用于状态显示
    stages.append(("数据库同步", "synced"))

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


def _finish_pipeline_command(
    result,
    *,
    ctx: typer.Context | None = None,
    report_sink=None,
):
    if (
        report_sink is not None
        and report_sink.latest_report is not None
        and report_sink.latest_paths is not None
    ):
        _terminal_reporter(ctx).complete_report(
            report_sink.latest_report,
            report_sink.latest_paths.latest_markdown,
        )
        if result.status.value == "success":
            return
        raise typer.Exit(int(result.exit_code))
    if result.status.value == "success":
        console.print("[green]流水线完成[/green]")
        return
    if result.status.value == "interrupted":
        typer.echo("运行已中断", err=True)
    elif result.status.value == "degraded":
        typer.echo("流水线降级完成", err=True)
    else:
        typer.echo("流水线失败", err=True)
    raise typer.Exit(int(result.exit_code))


def _terminal_reporter(ctx: typer.Context | None) -> TerminalReporter:
    options = None
    if ctx is not None:
        root_object = ctx.find_root().obj or {}
        options = root_object.get("terminal_options")
    quiet = bool(getattr(options, "quiet", False))
    no_progress = bool(getattr(options, "no_progress", False))
    no_color = bool(getattr(options, "no_color", False))
    mode = resolve_mode(
        json_output=False,
        quiet=quiet,
        no_progress=no_progress,
        is_tty=bool(getattr(sys.stderr, "isatty", lambda: False)()),
    )
    return TerminalReporter(
        SimpleNamespace(stdout=sys.stdout, stderr=sys.stderr),
        mode=mode,
        no_color=no_color,
    )


def _raise_pipeline_state_cli_error(exc: PipelineStateError) -> None:
    if isinstance(exc, PipelineStateCorruptError):
        typer.echo(f"state_corrupt: {exc}", err=True)
    elif isinstance(exc, ConcurrentRunError):
        typer.echo(str(exc), err=True)
    else:
        typer.echo(f"pipeline_state_error: {exc}", err=True)
    raise typer.Exit(1)


@app.command("full")
def cmd_full(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="小说文件路径"),
    start: int = typer.Option(None, "--start", "-s", min=1, help="起始章节号"),
    end: int = typer.Option(None, "--end", "-e", min=1, help="结束章节号"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
    use_window: bool = typer.Option(False, "--window", "-w", help="启用滑动窗口模式"),
    use_navigation: bool = typer.Option(False, "--navigation", help="强制执行前置导航"),
    skip_navigation: bool = typer.Option(False, "--skip-navigation", help="跳过前置导航"),
    mode: str = typer.Option("standard", "--mode", help="fast / standard / deep"),
    skip_sync: bool = typer.Option(False, "--skip-sync", help="跳过数据库同步"),
    skip_embedding: bool = typer.Option(False, "--skip-embedding", help="跳过章节向量化"),
):
    """使用统一阶段计划执行完整流水线。"""
    if start is not None and end is not None and end < start:
        raise typer.BadParameter("--end 必须大于等于 --start")
    if use_navigation and skip_navigation:
        raise typer.BadParameter("--navigation 与 --skip-navigation 不能同时使用")
    try:
        runtimes: list[PipelineRuntime] = []
        result = run_full_pipeline(
            file_path=file_path,
            start=start,
            end=end,
            provider=provider,
            use_window=use_window,
            use_navigation=use_navigation,
            skip_navigation=skip_navigation,
            mode=mode,
            skip_sync=skip_sync,
            skip_embedding=skip_embedding,
            runtime_observer=runtimes.append,
        )
    except PipelineStateError as exc:
        _raise_pipeline_state_cli_error(exc)
    except KeyboardInterrupt:
        typer.echo("运行已中断", err=True)
        raise typer.Exit(130) from None
    report_sink = runtimes[-1].report_sink if runtimes else None
    _finish_pipeline_command(result, ctx=ctx, report_sink=report_sink)


@app.command("continue")
def cmd_continue(
    ctx: typer.Context,
    material_id: str = typer.Argument(..., help="素材 ID"),
    skip_sync: bool = typer.Option(False, "--skip-sync", help="跳过数据库同步"),
    start: int = typer.Option(None, "--start", "-s", min=1, help="起始章节号"),
    end: int = typer.Option(None, "--end", "-e", min=1, help="结束章节号"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
    use_window: bool = typer.Option(False, "--window", "-w", help="启用滑动窗口模式"),
    use_navigation: bool = typer.Option(False, "--navigation", help="强制执行前置导航"),
    skip_navigation: bool = typer.Option(False, "--skip-navigation", help="跳过前置导航"),
    mode: str = typer.Option("standard", "--mode", help="fast / standard / deep"),
    skip_embedding: bool = typer.Option(False, "--skip-embedding", help="跳过章节向量化"),
):
    """使用持久化/legacy 检查生成统一续传计划。"""
    if start is not None and end is not None and end < start:
        raise typer.BadParameter("--end 必须大于等于 --start")
    if use_navigation and skip_navigation:
        raise typer.BadParameter("--navigation 与 --skip-navigation 不能同时使用")
    try:
        runtimes: list[PipelineRuntime] = []
        result = run_continue_pipeline(
            material_id=material_id,
            start=start,
            end=end,
            provider=provider,
            use_window=use_window,
            use_navigation=use_navigation,
            skip_navigation=skip_navigation,
            mode=mode,
            skip_sync=skip_sync,
            skip_embedding=skip_embedding,
            runtime_observer=runtimes.append,
        )
    except PipelineStateError as exc:
        _raise_pipeline_state_cli_error(exc)
    except KeyboardInterrupt:
        typer.echo("运行已中断", err=True)
        raise typer.Exit(130) from None
    report_sink = runtimes[-1].report_sink if runtimes else None
    _finish_pipeline_command(result, ctx=ctx, report_sink=report_sink)


@app.command("report")
def cmd_report(
    material_id: str = typer.Argument(..., help="素材 ID"),
    run_id: str | None = typer.Option(None, "--run-id", help="指定运行 ID"),
):
    """从结构化运行日志只读重建运行与产物质量报告。"""
    novel_dir = NOVELS_DIR / material_id
    try:
        target_run_id = run_id
        if target_run_id is None:
            target_run_id = PipelineStateStore(novel_dir).read_latest().run_id
        events = read_run_events(ensure_log_dir(), target_run_id)
        if not events:
            typer.echo("run_events_missing", err=True)
            raise typer.Exit(1)

        writer = ReportWriter(novel_dir)
        history = writer.load_history()
        completed_at = max(
            item.occurred_at
            for item in events
            if item.event_name == "RunCompleted"
        )
        comparable_history = tuple(
            item
            for item in history
            if item.run_id != target_run_id
            and item.completed_at <= completed_at
        )
        report = build_run_report(
            events,
            baseline_reports=comparable_history,
        )
        paths = writer.write(report)
    except typer.Exit:
        raise
    except PipelineStateError as exc:
        _raise_pipeline_state_cli_error(exc)
    except (
        ReportBuildError,
        ReportConflictError,
        ReportHistoryError,
        RunLogReadError,
        ValueError,
    ) as exc:
        typer.echo(f"report_rebuild_failed: {exc}", err=True)
        raise typer.Exit(1) from None

    typer.echo(str(paths.latest_markdown))
