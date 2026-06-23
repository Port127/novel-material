"""Validate 子命令：数据校验。"""
import typer
from rich.console import Console
from rich.table import Table

from novel_material.audit import audit_material, audit_run_status
from novel_material.runtime.contracts import RunStatus, exit_code_for
from novel_material.validation.schema import validate_material
from novel_material.validation.quality import run_quality_check
from novel_material.validation.insights import validate_material_insights

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

        results = []
        for novel_dir in NOVELS_DIR.iterdir():
            if novel_dir.is_dir():
                passed = validate_material(novel_dir.name, verbose=False)
                results.append({"material_id": novel_dir.name, "passed": passed})

        table = Table(title="校验结果汇总")
        table.add_column("素材", style="cyan")
        table.add_column("状态", style="green")

        for r in results:
            status = "[green]通过[/green]" if r["passed"] else "[red]失败[/red]"
            table.add_row(r["material_id"], status)

        console.print(table)
        if any(not result["passed"] for result in results):
            raise typer.Exit(1)

    elif material_id:
        result = validate_material(material_id)

        if result:
            console.print(f"[green]素材 {material_id} 校验通过[/green]")
        else:
            typer.echo(f"素材 {material_id} 校验失败", err=True)
            raise typer.Exit(1)

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

    if result:
        console.print(f"[green]素材 {material_id} 质量检查通过[/green]")
    else:
        console.print(f"[red]素材 {material_id} 质量检查失败[/red]")


@app.command("insights")
def cmd_validate_insights(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """校验 chapter_insights 深度分析结果。"""
    errors = validate_material_insights(material_id)
    if errors:
        for error in errors:
            console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(1)
    console.print(f"[green]素材 {material_id} 深度分析校验通过[/green]")


@app.command("artifacts")
def cmd_validate_artifacts(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """只读检查分析产物，不调用 LLM。"""
    audit = audit_material(material_id)
    for item in audit.issues:
        typer.echo(
            f"{item.severity.value}: {item.code}: {item.message}",
            err=True,
        )

    status = audit_run_status(audit)
    typer.echo(
        f"规则审计完成：{audit.summary}",
        err=status is not RunStatus.SUCCESS,
    )
    if status is not RunStatus.SUCCESS:
        raise typer.Exit(int(exit_code_for(status)))
