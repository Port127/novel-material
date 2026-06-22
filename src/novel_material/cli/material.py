"""Material 子命令：素材管理。"""
import json
import time
import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path

from novel_material.material.import_material import import_material
from novel_material.material.delete import delete_material
from novel_material.material.classify import (
    classify_book,
    get_status,
    load_novel_index,
    load_material_index,
    save_material_index,
    load_progress,
    save_progress,
    CLASSIFY_INDEX_FILE,
    CLASSIFY_PROGRESS_FILE,
    MATERIAL_DIR,
)
from novel_material.infra.config import NOVELS_DIR, INDEX_FILE
from novel_material.infra.yaml_io import load_yaml
from novel_material.infra.llm import load_config
from novel_material.terminal.eta import BatchEtaEstimator
from novel_material.runtime.context import run_context

app = typer.Typer(help="素材管理")
classify_app = typer.Typer(help="素材分类")
app.add_typer(classify_app, name="classify")
console = Console()


class _MonotonicClock:
    @staticmethod
    def monotonic() -> float:
        return time.monotonic()


def _print_classify_eta(estimator: BatchEtaEstimator, completed: int) -> None:
    snapshot = estimator.snapshot(completed=completed)
    if snapshot.remaining_seconds is None:
        console.print("  [dim]预计剩余: 估算中[/dim]")
        return
    console.print(f"  [dim]预计剩余: {snapshot.remaining_seconds / 60:.1f} 分钟[/dim]")


def list_materials():
    """列出所有素材。"""
    if INDEX_FILE.exists():
        index = load_yaml(INDEX_FILE)
        return [
            {
                "material_id": mid,
                "name": data.get("name", ""),
                "status": data.get("status", ""),
            }
            for mid, data in index.items()
        ]
    return []


@app.command("import")
def cmd_import(
    dir_path: str = typer.Argument(..., help="素材目录路径"),
):
    """批量导入素材目录。"""
    with run_context(command="material import"):
        count = import_material(dir_path)
    console.print(f"[green]成功导入 {count} 个素材[/green]")


@app.command("delete")
def cmd_delete(
    material_id: str = typer.Option(..., "--id", "-i", help="素材 ID"),
    force: bool = typer.Option(False, "--force", "-f", help="强制删除，不确认"),
):
    """删除素材。"""
    if not force:
        confirm = typer.confirm(f"确认删除素材 {material_id}?")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            raise typer.Exit(0)

    with run_context(command="material delete", material_id=material_id):
        result = delete_material(material_id, confirm=False)
    if result:
        console.print(f"[green]素材 {material_id} 已删除[/green]")
    else:
        typer.echo("删除失败", err=True)
        raise typer.Exit(1)


@app.command("list")
def cmd_list():
    """列出所有素材。"""
    materials = list_materials()

    if not materials:
        console.print("[yellow]无素材[/yellow]")
        return

    table = Table(title="素材列表")
    table.add_column("ID", style="cyan")
    table.add_column("名称", style="green")
    table.add_column("状态", style="yellow")

    for m in materials[:20]:
        table.add_row(
            m.get("material_id", ""),
            m.get("name", ""),
            m.get("status", "")
        )

    console.print(table)
    if len(materials) > 20:
        console.print(f"[dim]显示前 20 条，共 {len(materials)} 条[/dim]")


@classify_app.command("status")
def cmd_classify_status():
    """查看分类进度统计。"""
    status = get_status()

    console.print("\n[bold]分类进度统计[/bold]")
    console.print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    console.print(f"总素材数:    {status['total']}")
    console.print(f"已完成:      {status['processed']} ({status['progress_percent']}%)")
    console.print(f"剩余:        {status['remaining']}")
    console.print(f"失败:        {status['failed']}")

    if status['last_processed_file']:
        console.print(f"当前处理:    {status['last_processed_file']}")

    if status['last_processed_time']:
        console.print(f"上次处理:    {status['last_processed_time']}")

    console.print("预计剩余:    估算中（至少需要两个真实样本）")


@classify_app.command("start")
def cmd_classify_start(
    limit: int = typer.Option(0, "--limit", "-l", help="限制处理数量，0 表示全部"),
):
    """启动分类任务（从进度文件恢复）。"""
    novels = load_novel_index()
    progress = load_progress()
    material_index = load_material_index()

    # 确保顶层结构
    if "materials" not in material_index:
        material_index = {"materials": {}}

    start_seq = progress.get("last_processed_sequence", 0)
    total = len(novels)

    console.print(f"[bold]开始分类[/bold]")
    console.print(f"总素材数: {total}")
    console.print(f"起始位置: sequence={start_seq + 1}")

    if limit > 0:
        console.print(f"限制数量: {limit}")

    # 加载 LLM 配置
    config = load_config()

    processed = 0
    estimator = BatchEtaEstimator(clock=_MonotonicClock())
    estimator.start(total=max(total - start_seq, 0))
    for novel in novels:
        seq = novel.get("sequence", 0)
        if seq <= start_seq:
            continue

        if limit > 0 and processed >= limit:
            console.print(f"\n[yellow]已达到限制数量 {limit}[/yellow]")
            break

        title = novel.get("title", "未知")
        author = novel.get("author", "未知")
        file_name = f"{seq:04d}_{title}.txt"
        file_path = MATERIAL_DIR / file_name

        console.print(f"\n[cyan]处理 {seq}/{total}[/cyan]: {title}")

        # 检查文件是否存在
        if not file_path.exists():
            console.print(f"[red]文件不存在: {file_path}[/red]")
            progress["failed"].append({
                "sequence": seq,
                "title": title,
                "reason": "文件不存在",
            })
            progress["last_processed_sequence"] = seq
            progress["last_processed_file"] = file_name
            progress["last_processed_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            progress["processed"] = progress.get("processed", 0) + 1
            save_progress(progress)
            processed += 1
            estimator.complete_batch(items=1)
            _print_classify_eta(estimator, processed)
            continue

        # 执行分类
        try:
            result = classify_book(file_path, title, author, config)
        except Exception as e:
            console.print(f"[red]分类失败: {e}[/red]")
            progress["failed"].append({
                "sequence": seq,
                "title": title,
                "reason": str(e),
            })
            progress["last_processed_sequence"] = seq
            progress["last_processed_file"] = file_name
            progress["last_processed_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            progress["processed"] = progress.get("processed", 0) + 1
            save_progress(progress)
            processed += 1
            estimator.complete_batch(items=1)
            _print_classify_eta(estimator, processed)
            continue

        # 保存结果（新格式）
        material_index["materials"][f"{seq:04d}_{title}"] = {
            "title": title,
            "author": author,
            "file_path": str(file_path),
            "file_size": novel.get("file_size", 0),
            "download_count": novel.get("download_count", 0),
            # Genre（新格式）
            "genre_primary": result["genre_primary"],
            "genre_secondary": result.get("genre_secondary", ""),
            "genre_description": result.get("genre_description", ""),
            # Elements（批次3新增）
            "elements": result.get("elements", []),
            "elements_description": result.get("elements_description", ""),
            # Style（批次3新增）
            "style": result.get("style", {}),
            # Quality（批次3新增）
            "quality": result.get("quality", {}),
            # Meta
            "classification_status": result["status"],
            "classification_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "confidence": result.get("confidence", 0.0),
        }
        save_material_index(material_index)

        # 更新进度
        progress["last_processed_sequence"] = seq
        progress["last_processed_file"] = file_name
        progress["last_processed_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        progress["processed"] = progress.get("processed", 0) + 1
        progress["total"] = total
        progress["remaining"] = total - progress["processed"]
        save_progress(progress)

        console.print(f"  [green]分类完成[/green]: {result['genre_primary']}")
        if result["status"] == "low_confidence":
            console.print(f"  [yellow]置信度低[/yellow]: {result['confidence']}")

        processed += 1
        estimator.complete_batch(items=1)
        _print_classify_eta(estimator, processed)

    console.print(f"\n[bold green]分类完成[/bold green]")
    console.print(f"本次处理: {processed}")
    console.print(f"失败数量: {len(progress.get('failed', []))}")


@classify_app.command("retry")
def cmd_classify_retry(
    seq: int = typer.Option(None, "--seq", "-s", help="重试指定 sequence"),
    failed: bool = typer.Option(False, "--failed", "-f", help="重试所有失败条目"),
):
    """重试失败的分类任务。"""
    progress = load_progress()
    material_index = load_material_index()
    novels = load_novel_index()

    # 确保顶层结构
    if "materials" not in material_index:
        material_index = {"materials": {}}

    config = load_config()

    if seq is not None:
        # 重试指定 sequence
        novel = next((n for n in novels if n.get("sequence") == seq), None)
        if not novel:
            console.print(f"[red]找不到 sequence={seq}[/red]")
            return

        title = novel.get("title", "未知")
        author = novel.get("author", "未知")
        file_name = f"{seq:04d}_{title}.txt"
        file_path = MATERIAL_DIR / file_name

        console.print(f"[cyan]重试[/cyan]: {title}")

        if not file_path.exists():
            console.print(f"[red]文件不存在[/red]")
            return

        result = classify_book(file_path, title, author, config)

        # 保存结果（新格式）
        material_index["materials"][f"{seq:04d}_{title}"] = {
            "title": title,
            "author": author,
            "file_path": str(file_path),
            "file_size": novel.get("file_size", 0),
            "download_count": novel.get("download_count", 0),
            # Genre（新格式）
            "genre_primary": result["genre_primary"],
            "genre_secondary": result.get("genre_secondary", ""),
            "genre_description": result.get("genre_description", ""),
            # Elements
            "elements": result.get("elements", []),
            "elements_description": result.get("elements_description", ""),
            # Style
            "style": result.get("style", {}),
            # Quality
            "quality": result.get("quality", {}),
            # Meta
            "classification_status": result["status"],
            "classification_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "confidence": result.get("confidence", 0.0),
        }
        save_material_index(material_index)

        # 从 failed 列表移除
        progress["failed"] = [f for f in progress.get("failed", []) if f.get("sequence") != seq]
        save_progress(progress)

        console.print(f"[green]重试完成[/green]: {result['genre_primary']}")

    elif failed:
        # 重试所有失败条目
        failed_items = progress.get("failed", [])
        if not failed_items:
            console.print("[yellow]没有失败条目[/yellow]")
            return

        console.print(f"[bold]重试所有失败条目[/bold]: {len(failed_items)}")

        for item in failed_items:
            seq = item.get("sequence")
            title = item.get("title", "未知")

            novel = next((n for n in novels if n.get("sequence") == seq), None)
            if not novel:
                console.print(f"[red]找不到 novel: {title}[/red]")
                continue

            author = novel.get("author", "未知")
            file_name = f"{seq:04d}_{title}.txt"
            file_path = MATERIAL_DIR / file_name

            console.print(f"\n[cyan]重试[/cyan]: {title}")

            if not file_path.exists():
                console.print(f"[red]文件不存在[/red]")
                continue

            result = classify_book(file_path, title, author, config)

            # 保存结果（新格式）
            material_index["materials"][f"{seq:04d}_{title}"] = {
                "title": title,
                "author": author,
                "file_path": str(file_path),
                "file_size": novel.get("file_size", 0),
                "download_count": novel.get("download_count", 0),
                # Genre（新格式）
                "genre_primary": result["genre_primary"],
                "genre_secondary": result.get("genre_secondary", ""),
                "genre_description": result.get("genre_description", ""),
                # Elements
                "elements": result.get("elements", []),
                "elements_description": result.get("elements_description", ""),
                # Style
                "style": result.get("style", {}),
                # Quality
                "quality": result.get("quality", {}),
                # Meta
                "classification_status": result["status"],
                "classification_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "confidence": result.get("confidence", 0.0),
            }
            save_material_index(material_index)

            # 从 failed 列表移除
            progress["failed"] = [f for f in progress.get("failed", []) if f.get("sequence") != seq]

            # 更新进度统计
            progress["processed"] = progress.get("processed", 0) + 1
            remaining = progress.get("remaining", 0)
            if remaining > 0:
                progress["remaining"] = remaining - 1

            save_progress(progress)

            console.print(f"[green]重试完成[/green]: {result['genre_primary']}")

    else:
        console.print("[yellow]请指定 --seq 或 --failed[/yellow]")


@classify_app.command("clean")
def cmd_classify_clean(
    confirm: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
):
    """清空进度文件，重新开始。"""
    if not confirm:
        if not typer.confirm("确认清空分类进度?"):
            console.print("[yellow]已取消[/yellow]")
            return

    # 清空进度文件
    progress = {
        "last_processed_sequence": 0,
        "last_processed_file": "",
        "last_processed_time": "",
        "total": 0,
        "processed": 0,
        "remaining": 0,
        "failed": [],
    }
    save_progress(progress)
    console.print("[green]进度已清空[/green]")
