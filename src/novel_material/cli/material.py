"""Material 子命令：素材管理。"""
import typer
from rich.console import Console
from rich.table import Table

from novel_material.material.import_material import import_material
from novel_material.material.delete import delete_material
from novel_material.infra.config import NOVELS_DIR, INDEX_FILE
from novel_material.infra.yaml_io import load_yaml

app = typer.Typer(help="素材管理")
console = Console()


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
    count = import_material(dir_path)
    console.print(f"[green]成功导入 {count} 个素材[/green]")


@app.command("delete")
def cmd_delete(
    material_id: str = typer.Option(None, "--id", "-i", help="素材 ID"),
    force: bool = typer.Option(False, "--force", "-f", help="强制删除，不确认"),
):
    """删除素材。"""
    if not material_id:
        # 列出可选素材
        materials = list_materials()
        console.print("[yellow]请指定素材 ID[/yellow]")
        console.print("可用素材:")
        for m in materials[:10]:
            console.print(f"  [cyan]{m.get('material_id')}[/cyan] - {m.get('name')}")
        return

    if not force:
        confirm = typer.confirm(f"确认删除素材 {material_id}?")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            raise typer.Exit(0)

    result = delete_material(material_id, confirm=False)
    if result:
        console.print(f"[green]素材 {material_id} 已删除[/green]")
    else:
        console.print(f"[red]删除失败[/red]")


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