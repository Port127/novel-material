"""搜索响应的共用序列化。"""

import json

from novel_material.search.models import SearchResponse, SearchResult, SearchTrace


def build_response(query: str, results: list[SearchResult]) -> SearchResponse:
    """把兼容搜索函数的结果包装成统一响应。"""
    return SearchResponse(
        query=query,
        results=results,
        trace=SearchTrace(stages=["legacy"]),
    )


def response_json(response: SearchResponse) -> str:
    """输出保留中文、便于人工检查的稳定 JSON。"""
    return json.dumps(
        response.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )
