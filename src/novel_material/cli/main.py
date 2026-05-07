"""CLI 主入口：注册所有子命令。"""
import typer
from rich.console import Console

from .pipeline import app as pipeline_app
from .search import app as search_app
from .tags import app as tags_app
from .material import app as material_app
from .validate import app as validate_app
from .storage import app as storage_app

app = typer.Typer(
    name="nm",
    help="Novel Material - 小说素材管理 CLI",
    add_completion=False,
)
console = Console()

# 注册子命令
app.add_typer(pipeline_app, name="pipeline", help="数据处理流水线")
app.add_typer(search_app, name="search", help="素材检索")
app.add_typer(tags_app, name="tags", help="标签管理")
app.add_typer(material_app, name="material", help="素材管理")
app.add_typer(validate_app, name="validate", help="数据校验")
app.add_typer(storage_app, name="storage", help="数据库和存储管理")


@app.command()
def version():
    """显示版本信息。"""
    from novel_material import __version__
    console.print(f"[cyan]novel-material[/cyan] 版本 [green]{__version__}[/green]")


def main():
    """CLI 入口函数。"""
    # 启动时清理旧日志
    from novel_material.infra.logging_config import cleanup_old_logs
    cleanup_old_logs()
    app()


if __name__ == "__main__":
    main()