"""Storage 子命令：数据库和存储管理。"""
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from novel_material.storage.init_db import init_db
from novel_material.storage.init_data import init_data
from novel_material.storage.sync import sync_novel, sync_all

app = typer.Typer(help="数据库和存储管理")
console = Console()


@app.command("init-db")
def cmd_init_db():
    """初始化数据库表结构。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("初始化数据库...", total=None)
        init_db()
        progress.update(task, completed=True)

    console.print("[green]数据库初始化完成[/green]")


@app.command("init-data")
def cmd_init_data():
    """初始化基础数据（题材映射 + 标签字典）。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("初始化基础数据...", total=None)
        init_data()
        progress.update(task, completed=True)

    console.print("[green]基础数据初始化完成[/green]")


@app.command("init-tags")
def cmd_init_tags():
    """单独导入标签字典（从 data/tags.yaml）。"""
    from novel_material.storage.init_tags import init_tags

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("导入标签字典...", total=None)
        init_tags()
        progress.update(task, completed=True)

    console.print("[green]标签字典导入完成[/green]")


@app.command("sync")
def cmd_sync(
    material_id: str = typer.Argument(None, help="素材 ID（不指定则同步全部）"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称（用于修复时）"),
    use_window: bool = typer.Option(False, "--window", "-w", help="使用滑动窗口模式修复"),
):
    """同步素材到数据库。

    如果检测到质量问题（如 summary 长度不足），会自动尝试修复后重试。
    """
    if material_id:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"同步素材: {material_id}", total=None)
            success = sync_novel(material_id, provider=provider, use_window=use_window)
            progress.update(task, completed=True)

        if success:
            console.print(f"[green]素材 {material_id} 已同步[/green]")
        else:
            console.print(f"[red]素材 {material_id} 同步失败[/red]")
            console.print("[yellow]提示：检查日志排查问题，或手动修复后重试[/yellow]")
            raise typer.Exit(1)
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("同步全部素材...", total=None)
            count = sync_all()
            progress.update(task, completed=True)

        console.print(f"[green]已同步 {count} 个素材[/green]")