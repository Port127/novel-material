"""Search 子命令：素材检索。"""

from collections.abc import Callable

import typer
from rich.console import Console
from rich.table import Table

from novel_material.search.chapter import search_chapters
from novel_material.search.character import search_characters
from novel_material.search.detail import search_detail
from novel_material.search.event import search_events
from novel_material.search.insight import search_insights
from novel_material.search.models import SearchResult
from novel_material.search.outline import search_outlines
from novel_material.search.serialization import build_response, response_json
from novel_material.search.world import search_worldbuilding

app = typer.Typer(help="素材检索")
console = Console()


def _display_results(title: str, results: list[SearchResult]) -> None:
    """以统一表格展示结构化检索结果。"""
    table = Table(title=title)
    table.add_column("类型", style="cyan")
    table.add_column("标题", style="green")
    table.add_column("摘要", style="white")
    table.add_column("素材", style="dim")

    for result in results:
        summary = result.summary
        if len(summary) > 60:
            summary = summary[:60] + "..."
        table.add_row(
            result.document_type,
            result.title,
            summary,
            result.material_id,
        )

    console.print(table)
    console.print(f"[dim]共 {len(results)} 条结果[/dim]")


def _run_search(
    query: str,
    search_call: Callable[[], list[SearchResult]],
    *,
    json_output: bool,
    title: str,
) -> None:
    """统一处理搜索成功、空结果和异常。"""
    try:
        results = search_call()
    except Exception as exc:
        console.print(f"[red]检索失败：{exc}[/red]")
        raise typer.Exit(1) from exc

    response = build_response(query, results)
    if json_output:
        typer.echo(response_json(response))
    elif not results:
        console.print("[yellow]未找到匹配结果[/yellow]")
    else:
        _display_results(title, results)


@app.command("outline")
def cmd_outline(
    query: str | None = typer.Option(None, "--query", "-q", help="关键词"),
    genre: str | None = typer.Option(None, "--genre", "-g", help="题材筛选"),
    element: str | None = typer.Option(None, "--element", help="元素标签"),
    structure_type: str | None = typer.Option(None, "--structure", help="叙事结构"),
    premise_query: str | None = typer.Option(None, "--premise-query", help="前提关键词"),
    limit: int = typer.Option(5, "--limit", "-l", help="返回数量"),
    semantic: bool = typer.Option(False, "--semantic", help="启用语义检索"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索大纲。"""
    effective_query = premise_query or query or ""
    _run_search(
        effective_query,
        lambda: search_outlines(
            query=query,
            genre=genre,
            element=element,
            structure_type=structure_type,
            premise_query=premise_query,
            limit=limit,
            semantic=semantic,
        ),
        json_output=json_output,
        title="大纲检索结果",
    )


@app.command("character")
def cmd_character(
    query: str | None = typer.Option(None, "--query", "-q", help="关键词"),
    name: str | None = typer.Option(None, "--name", "-n", help="角色名"),
    archetype: str | None = typer.Option(None, "--archetype", "-a", help="原型类型"),
    role: str | None = typer.Option(None, "--role", "-r", help="角色定位"),
    genre: str | None = typer.Option(None, "--genre", "-g", help="题材筛选"),
    limit: int = typer.Option(10, "--limit", "-l", help="返回数量"),
    semantic: bool = typer.Option(False, "--semantic", help="启用语义检索"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索人物。"""
    effective_query = query or name or ""
    _run_search(
        effective_query,
        lambda: search_characters(
            query=query,
            name_query=name,
            archetype=archetype,
            role=role,
            genre=genre,
            limit=limit,
            semantic=semantic,
        ),
        json_output=json_output,
        title="人物检索结果",
    )


@app.command("chapter")
def cmd_chapter(
    keyword: str = typer.Argument(..., help="关键词"),
    genre: str | None = typer.Option(None, "--genre", "-g", help="题材筛选"),
    chapter_function: str | None = typer.Option(None, "--function", help="章节功能"),
    chapter_num: int | None = typer.Option(None, "--chapter", help="精确章节号"),
    tension_min: int | None = typer.Option(None, "--tension-min", help="最低张力"),
    tension_max: int | None = typer.Option(None, "--tension-max", help="最高张力"),
    element: str | None = typer.Option(None, "--element", help="元素标签"),
    style: str | None = typer.Option(None, "--style", help="风格标签"),
    plot_point: str | None = typer.Option(None, "--plot-point", help="结构角色"),
    limit: int = typer.Option(5, "--limit", "-l", help="返回数量"),
    semantic: bool = typer.Option(False, "--semantic", help="启用语义检索"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索章节摘要。"""
    _run_search(
        keyword,
        lambda: search_chapters(
            query=keyword,
            genre=genre,
            chapter_function=chapter_function,
            chapter_num=chapter_num,
            tension_min=tension_min,
            tension_max=tension_max,
            element=element,
            style=style,
            plot_point=plot_point,
            limit=limit,
            semantic=semantic,
        ),
        json_output=json_output,
        title="章节检索结果",
    )


@app.command("event")
def cmd_event(
    keyword: str = typer.Argument(..., help="事件描述"),
    setting: str | None = typer.Option(None, "--setting", help="场景类型"),
    emotion: str | None = typer.Option(None, "--emotion", help="情绪基调"),
    limit: int = typer.Option(10, "--limit", "-l", help="返回数量"),
    keyword_mode: bool = typer.Option(False, "--keyword", help="使用关键词检索"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索事件。"""
    _run_search(
        keyword,
        lambda: search_events(
            query=keyword,
            setting=setting,
            emotion=emotion,
            limit=limit,
            keyword=keyword_mode,
        ),
        json_output=json_output,
        title="事件检索结果",
    )


@app.command("world")
def cmd_world(
    keyword: str = typer.Argument(..., help="关键词"),
    dimension: str | None = typer.Option(None, "--dimension", "-d", help="维度筛选"),
    genre: str | None = typer.Option(None, "--genre", "-g", help="题材筛选"),
    importance: str | None = typer.Option(None, "--importance", help="重要性"),
    name: str | None = typer.Option(None, "--name", help="名称关键词"),
    limit: int = typer.Option(5, "--limit", "-l", help="返回数量"),
    semantic: bool = typer.Option(False, "--semantic", help="启用语义检索"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索世界观设定。"""
    _run_search(
        keyword,
        lambda: search_worldbuilding(
            query=keyword,
            entity_type=dimension,
            genre=genre,
            importance=importance,
            name_query=name,
            limit=limit,
            semantic=semantic,
        ),
        json_output=json_output,
        title="世界观检索结果",
    )


@app.command("detail")
def cmd_detail(
    keyword: str | None = typer.Argument(None, help="关键词"),
    genre: str | None = typer.Option(None, "--genre", "-g", help="题材筛选"),
    act: int | None = typer.Option(None, "--act", help="幕号"),
    description_query: str | None = typer.Option(None, "--query", "-q", help="描述关键词"),
    limit: int = typer.Option(10, "--limit", "-l", help="返回数量"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索细纲。"""
    effective_query = description_query or keyword or ""
    _run_search(
        effective_query,
        lambda: search_detail(
            query=keyword,
            genre=genre,
            act=act,
            description_query=description_query,
            limit=limit,
        ),
        json_output=json_output,
        title="细纲检索结果",
    )


@app.command("insight")
def cmd_insight(
    keyword: str = typer.Argument(..., help="关键词"),
    limit: int = typer.Option(10, "--limit", "-l", help="返回数量"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索 chapter_insights 深度分析。"""
    _run_search(
        keyword,
        lambda: search_insights(query=keyword, limit=limit),
        json_output=json_output,
        title="深度分析检索结果",
    )
