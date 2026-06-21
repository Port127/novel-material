"""质量优先检索的召回、融合、降级与时间预算编排。"""

from collections.abc import Callable
from time import perf_counter

from novel_material.search.fusion import diversify_results, reciprocal_rank_fusion
from novel_material.search.context import enrich_results_from_storage
from novel_material.search.chapter import (
    retrieve_chapters_lexical,
    retrieve_chapters_semantic,
    retrieve_chapters_structured,
)
from novel_material.search.character import (
    retrieve_characters_lexical,
    retrieve_characters_semantic,
    retrieve_characters_structured,
)
from novel_material.search.detail import (
    retrieve_details_lexical,
    retrieve_details_semantic,
    retrieve_details_structured,
)
from novel_material.search.event import (
    retrieve_events_lexical,
    retrieve_events_semantic,
    retrieve_events_structured,
)
from novel_material.search.insight import search_insights
from novel_material.search.models import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchTrace,
)
from novel_material.search.outline import (
    retrieve_outlines_lexical,
    retrieve_outlines_semantic,
    retrieve_outlines_structured,
)
from novel_material.search.world import (
    retrieve_worldbuilding_lexical,
    retrieve_worldbuilding_semantic,
    retrieve_worldbuilding_structured,
)

Retriever = Callable[[SearchRequest], list[SearchResult]]
ContextEnricher = Callable[[list[SearchResult], SearchTrace], list[SearchResult]]


def _retrieve_insights(request: SearchRequest) -> list[SearchResult]:
    return search_insights(request.query, limit=request.candidate_limit)


def _empty_retriever(_request: SearchRequest) -> list[SearchResult]:
    return []


DEFAULT_RETRIEVERS: dict[str, dict[str, Retriever]] = {
    "chapter": {
        "lexical": retrieve_chapters_lexical,
        "semantic": retrieve_chapters_semantic,
        "structured": retrieve_chapters_structured,
    },
    "event": {
        "lexical": retrieve_events_lexical,
        "semantic": retrieve_events_semantic,
        "structured": retrieve_events_structured,
    },
    "outline": {
        "lexical": retrieve_outlines_lexical,
        "semantic": retrieve_outlines_semantic,
        "structured": retrieve_outlines_structured,
    },
    "character": {
        "lexical": retrieve_characters_lexical,
        "semantic": retrieve_characters_semantic,
        "structured": retrieve_characters_structured,
    },
    "world": {
        "lexical": retrieve_worldbuilding_lexical,
        "semantic": retrieve_worldbuilding_semantic,
        "structured": retrieve_worldbuilding_structured,
    },
    "detail": {
        "lexical": retrieve_details_lexical,
        "semantic": retrieve_details_semantic,
        "structured": retrieve_details_structured,
    },
    "insight": {
        "lexical": _retrieve_insights,
        "semantic": _empty_retriever,
        "structured": _empty_retriever,
    },
}


class SearchServiceError(RuntimeError):
    """搜索服务无法返回任何可靠召回结果。"""


class SearchService:
    """编排词法、语义和结构化召回通道。"""

    def __init__(
        self,
        *,
        lexical: Retriever,
        semantic: Retriever,
        structured: Retriever,
        per_material_limit: int = 3,
        rrf_k: int = 60,
        clock: Callable[[], float] = perf_counter,
        context_enricher: ContextEnricher | None = None,
    ) -> None:
        self._retrievers = {
            "lexical": lexical,
            "semantic": semantic,
            "structured": structured,
        }
        self._per_material_limit = per_material_limit
        self._rrf_k = rrf_k
        self._clock = clock
        self._context_enricher = context_enricher

    def search(self, request: SearchRequest) -> SearchResponse:
        """执行请求；质量模式允许单路失败，精确模式只走语义召回。"""
        trace = SearchTrace()
        started_at = self._clock()
        stage_names = ["semantic"] if request.mode == "exact" else [
            "lexical",
            "semantic",
            "structured",
        ]
        ranked_results: dict[str, list[SearchResult]] = {}
        failures = 0

        for stage_name in stage_names:
            stage_started = self._clock()
            if stage_started - started_at >= request.time_budget_seconds:
                _degrade(trace, f"达到时间预算，跳过 {stage_name} 及后续阶段")
                break

            try:
                results = self._retrievers[stage_name](request)
            except Exception as exc:
                failures += 1
                _degrade(trace, f"{stage_name} 召回失败：{exc}")
                continue

            trace.elapsed_ms[stage_name] = (self._clock() - stage_started) * 1000
            trace.candidate_counts[stage_name] = len(results)
            trace.stages.append(stage_name)
            ranked_results[stage_name] = results

        if not ranked_results:
            if failures:
                raise SearchServiceError("全部召回通道失败")
            return SearchResponse(query=request.query, results=[], trace=trace)

        if request.mode == "exact":
            results = list(ranked_results["semantic"][: request.limit])
        else:
            fusion_started = self._clock()
            fused = reciprocal_rank_fusion(ranked_results, k=self._rrf_k)
            trace.elapsed_ms["fusion"] = (self._clock() - fusion_started) * 1000
            trace.stages.append("fusion")
            results = diversify_results(
                fused,
                limit=request.limit,
                per_material_limit=self._per_material_limit,
                material_id=request.filters.get("material_id"),
            )

        if self._context_enricher is not None:
            context_started = self._clock()
            if context_started - started_at < request.time_budget_seconds:
                results = self._context_enricher(results, trace)
                trace.elapsed_ms["context"] = (
                    self._clock() - context_started
                ) * 1000
                trace.stages.append("context")
            else:
                _degrade(trace, "达到时间预算，跳过 context 阶段")

        return SearchResponse(query=request.query, results=results, trace=trace)


def _degrade(trace: SearchTrace, reason: str) -> None:
    trace.degraded = True
    trace.degradation_reasons.append(reason)


def create_default_search_service(**kwargs) -> SearchService:
    """创建按 ``document_types`` 路由项目内置召回器的搜索服务。"""
    context_enricher = kwargs.pop("context_enricher", enrich_results_from_storage)

    def route(stage: str) -> Retriever:
        def retrieve(request: SearchRequest) -> list[SearchResult]:
            results: list[SearchResult] = []
            for document_type in request.document_types:
                results.extend(DEFAULT_RETRIEVERS[document_type][stage](request))
            return results

        return retrieve

    return SearchService(
        lexical=route("lexical"),
        semantic=route("semantic"),
        structured=route("structured"),
        context_enricher=context_enricher,
        **kwargs,
    )
