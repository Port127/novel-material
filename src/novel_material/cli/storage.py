"""Storage 子命令：数据库和存储管理。"""
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from novel_material.storage.init_db import init_db
from novel_material.storage.init_data import init_data
from novel_material.storage.sync import sync_novel, sync_all
from novel_material.storage.migrate import MigrationError, run_migrations
from novel_material.runtime.contracts import RunStatus
from novel_material.runtime.context import run_context

app = typer.Typer(help="数据库和存储管理")
console = Console()


@app.command("migrate")
def cmd_migrate():
    """按版本顺序升级已有数据库结构。"""
    try:
        with run_context(command="storage migrate"):
            versions = run_migrations()
    except MigrationError as exc:
        console.print(f"[red]数据库迁移失败：{exc}[/red]")
        raise typer.Exit(1) from exc

    if versions:
        console.print(f"[green]已应用迁移: {', '.join(versions)}[/green]")
    else:
        console.print("[green]无待执行迁移[/green]")


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
    repair: bool = typer.Option(False, "--repair", help="允许修改 YAML 并调用 LLM 修复"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过修复确认"),
):
    """同步素材到数据库。

    默认只校验并同步；检测到质量问题时不会自动修改素材。
    """
    if repair and not force:
        console.print("[yellow]警告：修复会修改 YAML、调用 LLM 并产生费用。[/yellow]")
        if not typer.confirm("确认授权修复并继续同步?"):
            console.print("[yellow]未执行同步[/yellow]")
            return

    if material_id:
        with run_context(command="storage sync", material_id=material_id):
            result = sync_novel(
                material_id,
                provider=provider,
                use_window=use_window,
                repair_allowed=repair,
            )

        if result.status is RunStatus.SUCCESS:
            console.print(f"[green]素材 {material_id} 已同步[/green]")
        else:
            typer.echo(f"素材 {material_id} 同步失败", err=True)
            for diagnostic in result.diagnostics:
                typer.echo(f"{diagnostic.code}: {diagnostic.message}", err=True)
            raise typer.Exit(1)
    else:
        summary = sync_all(
            provider=provider,
            use_window=use_window,
            repair_allowed=repair,
        )
        if summary.total == 0:
            console.print("[yellow]没有可同步素材[/yellow]")
            return
        message = (
            f"同步完成：总计 {summary.total}，成功 {summary.succeeded}，"
            f"失败 {summary.failed}，跳过 {summary.skipped}"
        )
        if summary.status is RunStatus.SUCCESS:
            console.print(f"[green]{message}[/green]")
            return
        typer.echo(message, err=True)
        raise typer.Exit(3 if summary.status is RunStatus.DEGRADED else 1)
