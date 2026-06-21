from collections.abc import Callable

import pytest

from novel_material.search.models import SearchRequest, SearchResult
from novel_material.search.service import SearchService, SearchServiceError


def result(result_id: str, material_id: str) -> SearchResult:
    return SearchResult(
        result_id=result_id,
        document_type="chapter",
        material_id=material_id,
    )


def test_quality_mode_runs_three_retrievers_and_fuses_results():
    service = SearchService(
        lexical=lambda _request: [result("a", "n1")],
        semantic=lambda _request: [result("b", "n2"), result("a", "n1")],
        structured=lambda _request: [result("c", "n3")],
    )

    response = service.search(SearchRequest(query="雨中告别", limit=3))

    assert response.results[0].result_id == "a"
    assert response.trace.candidate_counts == {
        "lexical": 1,
        "semantic": 2,
        "structured": 1,
    }
    assert response.trace.stages == ["lexical", "semantic", "structured", "fusion"]


def test_embedding_failure_degrades_to_lexical_and_structured():
    def fail(_request):
        raise RuntimeError("embedding unavailable")

    service = SearchService(
        lexical=lambda _request: [result("a", "n1")],
        semantic=fail,
        structured=lambda _request: [result("b", "n2")],
    )

    response = service.search(SearchRequest(query="宗门", limit=2))

    assert [item.result_id for item in response.results] == ["a", "b"]
    assert response.trace.degraded is True
    assert any("semantic" in reason for reason in response.trace.degradation_reasons)


def test_exact_mode_only_runs_semantic_retriever():
    calls: list[str] = []

    def retriever(name: str) -> Callable[[SearchRequest], list[SearchResult]]:
        def run(_request: SearchRequest) -> list[SearchResult]:
            calls.append(name)
            return [result(name, "n1")]

        return run

    service = SearchService(
        lexical=retriever("lexical"),
        semantic=retriever("semantic"),
        structured=retriever("structured"),
    )

    response = service.search(SearchRequest(query="宗门", mode="exact"))

    assert calls == ["semantic"]
    assert [item.result_id for item in response.results] == ["semantic"]


def test_all_quality_retrievers_failing_raises_service_error():
    def fail(_request):
        raise RuntimeError("unavailable")

    service = SearchService(lexical=fail, semantic=fail, structured=fail)

    with pytest.raises(SearchServiceError, match="全部召回通道失败"):
        service.search(SearchRequest(query="宗门"))


def test_time_budget_skips_remaining_retrievers():
    moments = iter([0.0, 0.1, 1.1, 1.2, 1.2, 1.2])
    calls: list[str] = []

    def lexical(_request):
        calls.append("lexical")
        return [result("a", "n1")]

    service = SearchService(
        lexical=lexical,
        semantic=lambda _request: calls.append("semantic") or [],
        structured=lambda _request: calls.append("structured") or [],
        clock=lambda: next(moments),
    )

    response = service.search(
        SearchRequest(query="宗门", limit=1, time_budget_seconds=1)
    )

    assert calls == ["lexical"]
    assert response.trace.degraded is True
    assert any("时间预算" in reason for reason in response.trace.degradation_reasons)
