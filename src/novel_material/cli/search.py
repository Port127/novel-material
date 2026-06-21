"""Search 子命令：素材检索。"""

import typer
from rich.console import Console
from rich.table import Table

from novel_material.search.models import SearchRequest, SearchResult
from novel_material.search.serialization import response_json
from novel_material.search.service import create_default_search_service

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
    request: SearchRequest,
    *,
    json_output: bool,
    title: str,
) -> None:
    """统一处理搜索成功、空结果和异常。"""
    try:
        response = create_default_search_service().search(request)
    except Exception as exc:
        console.print(f"[red]检索失败：{exc}[/red]")
        raise typer.Exit(1) from exc

    results = response.results
    if json_output:
        typer.echo(response_json(response))
    elif not results:
        console.print("[yellow]未找到匹配结果[/yellow]")
    else:
        _display_results(title, results)


def _filters(**values) -> dict:
    """移除未指定的 CLI 过滤条件。"""
    return {name: value for name, value in values.items() if value is not None}


def _request_options(
    *,
    semantic: bool,
    mode: str,
    candidate_limit: int,
    time_budget: int,
) -> dict:
    return {
        "mode": "exact" if semantic else mode,
        "candidate_limit": candidate_limit,
        "time_budget_seconds": time_budget,
    }


@app.command("outline")
def cmd_outline(
    query: str | None = typer.Option(None, "--query", "-q", help="关键词"),
    genre: str | None = typer.Option(None, "--genre", "-g", help="题材筛选"),
    element: str | None = typer.Option(None, "--element", help="元素标签"),
    structure_type: str | None = typer.Option(None, "--structure", help="叙事结构"),
    premise_query: str | None = typer.Option(None, "--premise-query", help="前提关键词"),
    limit: int = typer.Option(5, "--limit", "-l", help="返回数量"),
    semantic: bool = typer.Option(False, "--semantic", help="启用语义检索"),
    mode: str = typer.Option("quality", "--mode", help="quality 或 exact"),
    candidate_limit: int = typer.Option(200, "--candidate-limit", help="候选数量"),
    time_budget: int = typer.Option(180, "--time-budget", help="时间预算（秒）"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索大纲。"""
    effective_query = (
        premise_query or query or element or structure_type or genre or "大纲"
    )
    _run_search(
        SearchRequest(
            query=effective_query,
            document_types=["outline"],
            filters=_filters(
                genre=genre,
                element=element,
                structure_type=structure_type,
            ),
            limit=limit,
            **_request_options(semantic=semantic, mode=mode, candidate_limit=candidate_limit, time_budget=time_budget),
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
    mode: str = typer.Option("quality", "--mode", help="quality 或 exact"),
    candidate_limit: int = typer.Option(200, "--candidate-limit", help="候选数量"),
    time_budget: int = typer.Option(180, "--time-budget", help="时间预算（秒）"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索人物。"""
    effective_query = query or name or archetype or role or genre or "人物"
    _run_search(
        SearchRequest(
            query=effective_query,
            document_types=["character"],
            filters=_filters(
                name=name,
                archetype=archetype,
                role=role,
                genre=genre,
            ),
            limit=limit,
            **_request_options(semantic=semantic, mode=mode, candidate_limit=candidate_limit, time_budget=time_budget),
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
    mode: str = typer.Option("quality", "--mode", help="quality 或 exact"),
    candidate_limit: int = typer.Option(200, "--candidate-limit", help="候选数量"),
    time_budget: int = typer.Option(180, "--time-budget", help="时间预算（秒）"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索章节摘要。"""
    _run_search(
        SearchRequest(
            query=keyword,
            document_types=["chapter"],
            filters=_filters(
                genre=genre,
                chapter_function=chapter_function,
                chapter_num=chapter_num,
                tension_min=tension_min,
                tension_max=tension_max,
                element=element,
                style=style,
                plot_point=plot_point,
            ),
            limit=limit,
            **_request_options(semantic=semantic, mode=mode, candidate_limit=candidate_limit, time_budget=time_budget),
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
    mode: str = typer.Option("quality", "--mode", help="quality 或 exact"),
    candidate_limit: int = typer.Option(200, "--candidate-limit", help="候选数量"),
    time_budget: int = typer.Option(180, "--time-budget", help="时间预算（秒）"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索事件。"""
    _run_search(
        SearchRequest(
            query=keyword,
            document_types=["event"],
            filters=_filters(setting=setting, emotion=emotion),
            limit=limit,
            **_request_options(semantic=False, mode=mode, candidate_limit=candidate_limit, time_budget=time_budget),
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
    mode: str = typer.Option("quality", "--mode", help="quality 或 exact"),
    candidate_limit: int = typer.Option(200, "--candidate-limit", help="候选数量"),
    time_budget: int = typer.Option(180, "--time-budget", help="时间预算（秒）"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索世界观设定。"""
    _run_search(
        SearchRequest(
            query=keyword,
            document_types=["world"],
            filters=_filters(
                dimension=dimension,
                genre=genre,
                importance=importance,
                name=name,
            ),
            limit=limit,
            **_request_options(semantic=semantic, mode=mode, candidate_limit=candidate_limit, time_budget=time_budget),
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
    mode: str = typer.Option("quality", "--mode", help="quality 或 exact"),
    candidate_limit: int = typer.Option(200, "--candidate-limit", help="候选数量"),
    time_budget: int = typer.Option(180, "--time-budget", help="时间预算（秒）"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索细纲。"""
    effective_query = description_query or keyword or genre or "细纲"
    _run_search(
        SearchRequest(
            query=effective_query,
            document_types=["detail"],
            filters=_filters(genre=genre, act=act),
            limit=limit,
            **_request_options(semantic=False, mode=mode, candidate_limit=candidate_limit, time_budget=time_budget),
        ),
        json_output=json_output,
        title="细纲检索结果",
    )


@app.command("insight")
def cmd_insight(
    keyword: str = typer.Argument(..., help="关键词"),
    limit: int = typer.Option(10, "--limit", "-l", help="返回数量"),
    mode: str = typer.Option("quality", "--mode", help="quality 或 exact"),
    candidate_limit: int = typer.Option(200, "--candidate-limit", help="候选数量"),
    time_budget: int = typer.Option(180, "--time-budget", help="时间预算（秒）"),
    json_output: bool = typer.Option(False, "--json", help="输出稳定 JSON"),
):
    """检索 chapter_insights 深度分析。"""
    _run_search(
        SearchRequest(
            query=keyword,
            document_types=["insight"],
            limit=limit,
            **_request_options(semantic=False, mode=mode, candidate_limit=candidate_limit, time_budget=time_budget),
        ),
        json_output=json_output,
        title="深度分析检索结果",
    )
