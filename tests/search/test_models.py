"""统一搜索数据模型测试。"""

import pytest
from pydantic import ValidationError

from novel_material.search.models import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchTrace,
    SourceLocation,
)


def test_search_request_rejects_candidate_limit_below_limit():
    """候选数量不得小于最终返回数量。"""
    with pytest.raises(ValidationError):
        SearchRequest(query="雨中告别", limit=10, candidate_limit=5)


def test_search_response_serializes_stable_agent_contract():
    """响应应序列化为稳定的 Agent JSON 契约。"""
    result = SearchResult(
        result_id="chapter:nm_demo:7",
        document_type="chapter",
        material_id="nm_demo",
        chapter=7,
        title="第七章 告别",
        summary="主角在雨中向导师告别。",
        source=SourceLocation(chapter=7, start_line=101, end_line=160),
        scores={"semantic": 0.91},
        matched_fields=["summary"],
    )
    response = SearchResponse(
        query="雨中告别",
        results=[result],
        trace=SearchTrace(stages=["semantic"], elapsed_ms={"semantic": 12.5}),
    )

    payload = response.model_dump(mode="json")

    assert payload["results"][0]["result_id"] == "chapter:nm_demo:7"
    assert payload["trace"]["degraded"] is False
