"""Validate 子命令：数据校验。"""
import typer
from rich.console import Console
from rich.table import Table

from novel_material.validation.schema import validate_material
from novel_material.validation.quality import run_quality_check

app = typer.Typer(help="数据校验")
console = Console()


@app.command()
def validate(
    material_id: str = typer.Argument(None, help="素材 ID"),
    all: bool = typer.Option(False, "--all", "-a", help="校验全部素材"),
):
    """校验素材数据完整性。"""
    if all:
        from novel_material.infra.config import NOVELS_DIR
        from pathlib import Path

        results = []
        for novel_dir in NOVELS_DIR.iterdir():
            if novel_dir.is_dir():
                result = validate_material(novel_dir.name)
                results.append(result)

        table = Table(title="校验结果汇总")
        table.add_column("素材", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("错误数", style="red")

        for r in results:
            status = "[green]通过[/green]" if r.get("valid") else "[red]失败[/red]"
            table.add_row(
                r.get("material_id", ""),
                status,
                str(len(r.get("errors", [])))
            )

        console.print(table)

    elif material_id:
        result = validate_material(material_id)

        if result:
            console.print(f"[green]素材 {material_id} 校验通过[/green]")
        else:
            console.print(f"[red]素材 {material_id} 校验失败[/red]")

    else:
        console.print("[yellow]请指定素材 ID 或使用 --all[/yellow]")
        raise typer.Exit(1)


@app.command("quality")
def cmd_quality(
    material_id: str = typer.Argument(..., help="素材 ID"),
    start: int = typer.Option(None, "--start", "-s", help="起始章节号"),
    end: int = typer.Option(None, "--end", "-e", help="结束章节号"),
):
    """质量检查（支持指定章节范围）。"""
    # 参数验证
    if start is not None and start < 1:
        console.print("[red]起始章节号必须 >= 1[/red]")
        raise typer.Exit(1)
    if start is not None and end is not None and end < start:
        console.print("[red]结束章节号必须 >= 起始章节号[/red]")
        raise typer.Exit(1)

    result = run_quality_check(material_id, start_ch=start, end_ch=end)

    table = Table(title="质量检查结果")
    table.add_column("维度", style="cyan")
    table.add_column("得分", style="green")
    table.add_column("说明", style="white")

    for dim, data in result.items():
        if isinstance(data, dict):
            table.add_row(
                dim,
                str(data.get("score", 0)),
                data.get("note", "")
            )

    console.print(table)