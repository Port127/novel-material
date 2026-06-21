"""Eval 子命令：检索质量评测。"""

from dataclasses import replace
from pathlib import Path

import typer
from rich.console import Console

from novel_material.eval.search_eval import (
    SearchEvalCase,
    evaluate_cases,
    export_candidates,
    import_candidate_labels,
    load_search_cases,
    write_report,
)
from novel_material.search.chapter import search_chapters
from novel_material.search.character import search_characters
from novel_material.search.detail import search_detail
from novel_material.search.event import search_events
from novel_material.search.insight import search_insights
from novel_material.search.models import SearchResult
from novel_material.search.outline import search_outlines
from novel_material.search.world import search_worldbuilding

app = typer.Typer(help="质量评测")
search_app = typer.Typer(help="搜索质量评测")
console = Console()
app.add_typer(search_app, name="search")


def _filtered(filters: dict, *names: str) -> dict:
    """只把目标兼容搜索函数支持的过滤条件向下传递。"""
    return {name: filters[name] for name in names if name in filters}


def _search_case(
    case: SearchEvalCase,
    limit: int,
    mode: str,
) -> list[SearchResult]:
    """在混合服务落地前按类型调用现有精确兼容检索。"""
    semantic = mode in {"exact", "quality"}
    filters = case.filters

    if case.document_type == "chapter":
        return search_chapters(
            query=case.query,
            limit=limit,
            semantic=semantic,
            **_filtered(
                filters,
                "genre",
                "chapter_function",
                "chapter_num",
                "tension_min",
                "tension_max",
                "element",
                "style",
                "plot_point",
            ),
        )
    if case.document_type == "event":
        return search_events(
            query=case.query,
            limit=limit,
            keyword=False,
            **_filtered(filters, "setting", "emotion"),
        )
    if case.document_type == "outline":
        return search_outlines(
            query=case.query,
            limit=limit,
            semantic=semantic,
            **_filtered(filters, "genre", "element", "structure_type", "premise_query"),
        )
    if case.document_type == "character":
        return search_characters(
            query=case.query,
            limit=limit,
            semantic=semantic,
            **_filtered(filters, "archetype", "role", "genre", "name_query"),
        )
    if case.document_type == "world":
        return search_worldbuilding(
            query=case.query,
            limit=limit,
            semantic=semantic,
            **_filtered(filters, "entity_type", "genre", "importance", "name_query"),
        )
    if case.document_type == "detail":
        return search_detail(
            query=case.query,
            limit=limit,
            **_filtered(filters, "genre", "act", "description_query"),
        )
    if case.document_type == "insight":
        return search_insights(query=case.query, limit=limit)
    raise ValueError(f"不支持的 document_type: {case.document_type}")


def _search_inventory_case(
    case: SearchEvalCase,
    limit: int,
    mode: str,
) -> list[SearchResult]:
    """只为细纲标注池提供无关键词库存候选。"""
    if case.document_type != "detail":
        return []
    return _search_case(replace(case, query="", filters={}), limit, mode)


def _validate_mode(mode: str) -> None:
    if mode not in {"exact", "quality"}:
        raise ValueError("mode 必须是 exact 或 quality")


@search_app.command("prepare")
def prepare(
    queries: Path = typer.Option(..., "--queries", help="Golden Query YAML"),
    output: Path = typer.Option(..., "--output", help="候选标注 YAML"),
    limit: int = typer.Option(30, "--limit", min=1, max=100, help="每条查询候选数"),
    mode: str = typer.Option("exact", "--mode", help="exact 或 quality"),
):
    """执行检索并导出待人工标注候选。"""
    try:
        _validate_mode(mode)
        cases = load_search_cases(queries)
        export_candidates(
            cases,
            lambda case, candidate_limit: _search_case(
                case, candidate_limit, mode
            ),
            output,
            limit=limit,
            minimum_candidates=min(10, limit),
            relaxed_search_callable=lambda case, candidate_limit: _search_case(
                replace(case, filters={}),
                candidate_limit,
                mode,
            ),
            inventory_search_callable=lambda case, candidate_limit: (
                _search_inventory_case(case, candidate_limit, mode)
            ),
        )
    except Exception as exc:
        console.print(f"[red]候选导出失败：{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]已导出 {len(cases)} 条查询的候选：{output}[/green]")


@search_app.command("import-labels")
def import_labels(
    queries: Path = typer.Option(..., "--queries", help="Golden Query YAML"),
    candidates: Path = typer.Option(..., "--candidates", help="已人工标注候选 YAML"),
):
    """将 0～3 分人工标签合并回 Golden Query。"""
    try:
        import_candidate_labels(queries, candidates)
    except Exception as exc:
        console.print(f"[red]标签导入失败：{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]人工标签已合并：{queries}[/green]")


@search_app.command("score")
def score(
    queries: Path = typer.Option(..., "--queries", help="已标注 Golden Query YAML"),
    output: Path = typer.Option(..., "--output", help="JSON 评测报告"),
    mode: str = typer.Option("exact", "--mode", help="exact 或 quality"),
):
    """执行检索并输出逐查询、分类型和总体指标。"""
    try:
        _validate_mode(mode)
        cases = load_search_cases(queries)
        report = evaluate_cases(
            cases,
            lambda case, candidate_limit: _search_case(
                case, candidate_limit, mode
            ),
        )
        write_report(report, output)
    except Exception as exc:
        console.print(f"[red]检索评分失败：{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]评测报告已写入：{output}[/green]")
