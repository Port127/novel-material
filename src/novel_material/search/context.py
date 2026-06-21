"""为章节类检索结果补充邻章摘要和原文位置。"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from psycopg2.extras import RealDictCursor

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml_list
from novel_material.search.db import readonly_connection
from novel_material.search.models import (
    NeighborContext,
    SearchResult,
    SearchTrace,
    SourceLocation,
)

_CONTEXT_TYPES = {"chapter", "event", "insight"}


def enrich_chapter_result(
    result: SearchResult,
    *,
    summaries: Mapping[int, str],
    novels_dir: Path,
    index_cache: dict[str, dict[int, dict[str, Any]]] | None = None,
    trace: SearchTrace | None = None,
) -> SearchResult:
    """补充单条章节类结果，且不修改调用方传入的对象。"""
    enriched = result.model_copy(deep=True)
    if result.document_type not in _CONTEXT_TYPES or result.chapter is None:
        return enriched

    chapter = result.chapter
    enriched.neighbors = NeighborContext(
        previous_summary=summaries.get(chapter - 1),
        next_summary=summaries.get(chapter + 1),
    )

    cache = index_cache if index_cache is not None else {}
    chapter_index = _chapter_index(result.material_id, novels_dir, cache)
    location = chapter_index.get(chapter)
    if location is not None:
        enriched.source = SourceLocation(
            chapter=chapter,
            start_line=_optional_int(location.get("start_line")),
            end_line=_optional_int(location.get("end_line")),
        )
    elif enriched.source is None:
        enriched.source = SourceLocation(chapter=chapter)
        _record_degradation(trace, f"{result.result_id} 缺少 chapter_index 定位")

    if chapter > 1 and enriched.neighbors.previous_summary is None:
        _record_degradation(trace, f"{result.result_id} 缺少前章摘要")
    if chapter_index and chapter < max(chapter_index) and enriched.neighbors.next_summary is None:
        _record_degradation(trace, f"{result.result_id} 缺少后章摘要")
    return enriched


def enrich_chapter_results(
    results: Sequence[SearchResult],
    *,
    summaries_by_material: Mapping[str, Mapping[int, str]],
    novels_dir: Path,
    trace: SearchTrace | None = None,
) -> list[SearchResult]:
    """批量补充结果，并复用同一素材的章节索引缓存。"""
    index_cache: dict[str, dict[int, dict[str, Any]]] = {}
    return [
        enrich_chapter_result(
            result,
            summaries=summaries_by_material.get(result.material_id, {}),
            novels_dir=novels_dir,
            index_cache=index_cache,
            trace=trace,
        )
        for result in results
    ]


def enrich_results_from_storage(
    results: Sequence[SearchResult],
    trace: SearchTrace,
    *,
    novels_dir: Path = NOVELS_DIR,
) -> list[SearchResult]:
    """一次查询加载全部命中所需邻章摘要，再补充本地原文位置。"""
    chapter_results = [
        result
        for result in results
        if result.document_type in _CONTEXT_TYPES and result.chapter is not None
    ]
    if not chapter_results:
        return [result.model_copy(deep=True) for result in results]

    material_ids = sorted({result.material_id for result in chapter_results})
    chapter_numbers = sorted({
        neighbor
        for result in chapter_results
        for neighbor in (result.chapter - 1, result.chapter, result.chapter + 1)
        if neighbor >= 1
    })
    summaries_by_material: dict[str, dict[int, str]] = {}
    try:
        with readonly_connection() as conn, conn.cursor(
            cursor_factory=RealDictCursor
        ) as cur:
            cur.execute(
                """
                SELECT material_id, chapter, summary
                FROM chapters
                WHERE material_id = ANY(%s) AND chapter = ANY(%s)
                """,
                (material_ids, chapter_numbers),
            )
            rows = cur.fetchall()
        for row in rows:
            summaries_by_material.setdefault(row["material_id"], {})[
                int(row["chapter"])
            ] = row.get("summary") or ""
    except Exception as exc:
        _record_degradation(trace, f"邻章摘要查询失败：{exc}")

    return enrich_chapter_results(
        results,
        summaries_by_material=summaries_by_material,
        novels_dir=novels_dir,
        trace=trace,
    )


def _chapter_index(
    material_id: str,
    novels_dir: Path,
    cache: dict[str, dict[int, dict[str, Any]]],
) -> dict[int, dict[str, Any]]:
    if material_id not in cache:
        entries = load_yaml_list(novels_dir / material_id / "chapter_index.yaml")
        cache[material_id] = {
            chapter: entry
            for entry in entries
            if isinstance(entry, dict)
            and (chapter := _optional_int(entry.get("chapter"))) is not None
        }
    return cache[material_id]


def _record_degradation(trace: SearchTrace | None, reason: str) -> None:
    if trace is None or reason in trace.degradation_reasons:
        return
    trace.degraded = True
    trace.degradation_reasons.append(reason)


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
