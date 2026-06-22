from collections.abc import Callable

import pytest

from novel_material.search.models import SearchRequest, SearchResult
from novel_material.search.service import (
    DEFAULT_RETRIEVERS,
    SearchService,
    SearchServiceError,
    create_default_search_service,
)
from novel_material.runtime.context import run_context
from novel_material.runtime.dispatcher import RuntimeDispatcher
from novel_material.runtime.testing import MemoryEventSink


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


def test_default_service_routes_only_requested_document_types(monkeypatch):
    calls: list[tuple[str, str]] = []

    def routed(document_type: str, stage: str):
        def retrieve(_request):
            calls.append((document_type, stage))
            return [result(f"{document_type}:{stage}", document_type)]

        return retrieve

    for document_type in ("chapter", "world"):
        for stage in ("lexical", "semantic", "structured"):
            monkeypatch.setitem(
                DEFAULT_RETRIEVERS[document_type],
                stage,
                routed(document_type, stage),
            )

    service = create_default_search_service(context_enricher=None)
    service.search(
        SearchRequest(
            query="宗门",
            document_types=["chapter", "world"],
            limit=3,
        )
    )

    assert set(calls) == {
        (document_type, stage)
        for document_type in ("chapter", "world")
        for stage in ("lexical", "semantic", "structured")
    }


def test_service_applies_context_enricher_after_diversity():
    received: list[str] = []

    def enrich(results, trace):
        received.extend(item.result_id for item in results)
        enriched = [item.model_copy(deep=True) for item in results]
        enriched[0].rank_reason = "已补充上下文"
        return enriched

    service = SearchService(
        lexical=lambda _request: [result("a", "n1")],
        semantic=lambda _request: [],
        structured=lambda _request: [],
        context_enricher=enrich,
    )

    response = service.search(SearchRequest(query="宗门", limit=1))

    assert received == ["a"]
    assert response.results[0].rank_reason == "已补充上下文"
    assert response.trace.stages[-1] == "context"


def test_reranker_failure_returns_fused_order_and_records_degradation():
    class FailingReranker:
        def rerank(self, *_args, **_kwargs):
            raise RuntimeError("invalid JSON")

    service = SearchService(
        lexical=lambda _request: [result("a", "n1")],
        semantic=lambda _request: [result("b", "n2"), result("a", "n1")],
        structured=lambda _request: [],
        reranker=FailingReranker(),
    )

    response = service.search(SearchRequest(query="宗门", limit=2))

    assert [item.result_id for item in response.results] == ["a", "b"]
    assert response.trace.degraded is True
    assert any("rerank_failed" in reason for reason in response.trace.degradation_reasons)


def test_default_service_rejects_unknown_configured_reranker(monkeypatch):
    service_module = __import__("novel_material.search.service", fromlist=["service"])
    monkeypatch.setattr(
        service_module,
        "get_settings",
        lambda: {"SEARCH_RERANKER": "unknown"},
        raising=False,
    )

    with pytest.raises(ValueError, match="SEARCH_RERANKER"):
        create_default_search_service(context_enricher=None)


def test_search_emits_channel_counts_and_degradation_without_query_text():
    def fail(_request):
        raise TimeoutError("slow")

    sink = MemoryEventSink()
    service = SearchService(
        lexical=lambda _request: [result("a", "n1")],
        semantic=fail,
        structured=lambda _request: [],
        dispatcher=RuntimeDispatcher([sink]),
    )

    with run_context(command="search chapter"):
        response = service.search(SearchRequest(query="不可写入日志的宗门正文"))

    completed = [event for event in sink.events if event.event_name == "OperationCompleted"][-1]
    assert completed.attributes["mode"] == "quality"
    assert completed.attributes["candidate_counts"]["lexical"] == 1
    assert completed.attributes["degraded"] is True
    assert any("semantic" in reason for reason in completed.attributes["degradation_reasons"])
    assert completed.attributes["query_length"] == len("不可写入日志的宗门正文")
    assert "不可写入日志的宗门正文" not in completed.model_dump_json()
    assert response.trace.degraded is True
