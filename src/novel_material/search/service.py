"""质量优先检索的召回、融合、降级与时间预算编排。"""

from collections.abc import Callable
from time import perf_counter

from novel_material.search.fusion import diversify_results, reciprocal_rank_fusion
from novel_material.search.models import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchTrace,
)

Retriever = Callable[[SearchRequest], list[SearchResult]]


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
    ) -> None:
        self._retrievers = {
            "lexical": lexical,
            "semantic": semantic,
            "structured": structured,
        }
        self._per_material_limit = per_material_limit
        self._rrf_k = rrf_k
        self._clock = clock

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

        return SearchResponse(query=request.query, results=results, trace=trace)


def _degrade(trace: SearchTrace, reason: str) -> None:
    trace.degraded = True
    trace.degradation_reasons.append(reason)
