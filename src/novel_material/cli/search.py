"""Search 子命令：素材检索。"""
import typer
from rich.console import Console
from rich.table import Table

from novel_material.search.outline import search_outlines
from novel_material.search.character import search_characters
from novel_material.search.chapter import search_chapters
from novel_material.search.world import search_worldbuilding
from novel_material.search.insight import search_insights

app = typer.Typer(help="素材检索")
console = Console()


@app.command("outline")
def cmd_outline(
    query: str = typer.Option(None, "--query", "-q", help="关键词"),
    genre: str = typer.Option(None, "--genre", "-g", help="题材筛选"),
    limit: int = typer.Option(5, "--limit", "-l", help="返回数量"),
):
    """检索大纲。"""
    results = search_outlines(query=query, genre=genre, limit=limit)

    if not results:
        console.print("[yellow]未找到匹配结果[/yellow]")
        return

    table = Table(title="大纲检索结果")
    table.add_column("名称", style="cyan")
    table.add_column("题材", style="green")
    table.add_column("前提", style="white")

    for r in results:
        table.add_row(
            r.get("name", ""),
            r.get("genre", ""),
            r.get("premise", "")[:50] + "..." if r.get("premise") else ""
        )

    console.print(table)
    console.print(f"[dim]共 {len(results)} 条结果[/dim]")


@app.command("character")
def cmd_character(
    name: str = typer.Option(None, "--name", "-n", help="角色名"),
    archetype: str = typer.Option(None, "--archetype", "-a", help="原型类型"),
    role: str = typer.Option(None, "--role", "-r", help="角色定位"),
    limit: int = typer.Option(10, "--limit", "-l", help="返回数量"),
):
    """检索人物。"""
    results = search_characters(name_query=name, archetype=archetype, role=role, limit=limit)

    if not results:
        console.print("[yellow]未找到匹配结果[/yellow]")
        return

    table = Table(title="人物检索结果")
    table.add_column("名称", style="cyan")
    table.add_column("角色", style="green")
    table.add_column("原型", style="yellow")
    table.add_column("素材", style="dim")

    for r in results:
        table.add_row(
            r.get("name", ""),
            r.get("role", ""),
            r.get("archetype", ""),
            r.get("material_id", "")
        )

    console.print(table)
    console.print(f"[dim]共 {len(results)} 条结果[/dim]")


@app.command("chapter")
def cmd_chapter(
    keyword: str = typer.Argument(..., help="关键词"),
    limit: int = typer.Option(5, "--limit", "-l", help="返回数量"),
):
    """检索章节摘要。"""
    results = search_chapters(query=keyword, limit=limit)

    if not results:
        console.print("[yellow]未找到匹配结果[/yellow]")
        return

    table = Table(title="章节检索结果")
    table.add_column("章节", style="cyan")
    table.add_column("标题", style="green")
    table.add_column("摘要", style="white")
    table.add_column("素材", style="dim")

    for r in results:
        summary = r.get("summary", "")
        if len(summary) > 60:
            summary = summary[:60] + "..."
        table.add_row(
            str(r.get("chapter", "")),
            r.get("title", ""),
            summary,
            r.get("material_id", "")
        )

    console.print(table)
    console.print(f"[dim]共 {len(results)} 条结果[/dim]")


@app.command("world")
def cmd_world(
    keyword: str = typer.Argument(..., help="关键词"),
    dimension: str = typer.Option(None, "--dimension", "-d", help="维度筛选"),
    limit: int = typer.Option(5, "--limit", "-l", help="返回数量"),
):
    """检索世界观设定。"""
    results = search_worldbuilding(query=keyword, entity_type=dimension, limit=limit)

    if not results:
        console.print("[yellow]未找到匹配结果[/yellow]")
        return

    table = Table(title="世界观检索结果")
    table.add_column("类型", style="cyan")
    table.add_column("名称", style="green")
    table.add_column("描述", style="white")
    table.add_column("素材", style="dim")

    for r in results:
        desc = r.get("description", "")
        if len(desc) > 50:
            desc = desc[:50] + "..."
        table.add_row(
            r.get("type", ""),
            r.get("name", ""),
            desc,
            r.get("material_id", "")
        )

    console.print(table)
    console.print(f"[dim]共 {len(results)} 条结果[/dim]")


@app.command("insight")
def cmd_insight(
    keyword: str = typer.Argument(..., help="关键词"),
    limit: int = typer.Option(10, "--limit", "-l", help="返回数量"),
):
    """检索 chapter_insights 深度分析。"""
    results = search_insights(query=keyword, limit=limit)

    if not results:
        console.print("[yellow]未找到匹配结果[/yellow]")
        return

    table = Table(title="深度分析检索结果")
    table.add_column("章节", style="cyan")
    table.add_column("标题", style="green")
    table.add_column("命中字段", style="yellow")
    table.add_column("writing_takeaway", style="white")
    table.add_column("素材", style="dim")

    for r in results:
        takeaway = r.get("writing_takeaway", "")
        if len(takeaway) > 60:
            takeaway = takeaway[:60] + "..."
        table.add_row(
            str(r.get("chapter", "")),
            r.get("title", ""),
            ", ".join(r.get("matched_fields", [])),
            takeaway,
            r.get("material_id", ""),
        )

    console.print(table)
    console.print(f"[dim]共 {len(results)} 条结果[/dim]")
