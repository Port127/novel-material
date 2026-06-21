import pytest

from novel_material.search.models import SearchResult
from novel_material.search.rerank import IdentityReranker, LLMReranker, RerankError


def chapter(result_id: str) -> SearchResult:
    return SearchResult(
        result_id=result_id,
        document_type="chapter",
        material_id="nm_demo",
        summary=f"{result_id} 的摘要",
    )


def test_llm_reranker_uses_returned_scores_and_reasons():
    candidates = [chapter("a"), chapter("b")]
    reranker = LLMReranker(call=lambda *_args, **_kwargs: {
        "rankings": [
            {"result_id": "b", "score": 0.95, "reason": "情境和情绪都匹配"},
            {"result_id": "a", "score": 0.60, "reason": "只有事件相似"},
        ]
    })

    ranked = reranker.rerank("雨中告别", candidates, time_budget_seconds=30)

    assert [result.result_id for result in ranked] == ["b", "a"]
    assert ranked[0].rank_reason == "情境和情绪都匹配"
    assert ranked[0].scores["rerank"] == 0.95


@pytest.mark.parametrize(
    "payload",
    [
        {"rankings": []},
        {"rankings": [{"result_id": "unknown", "score": 0.5, "reason": "未知"}]},
        {"rankings": [{"result_id": "a", "score": 1.5, "reason": "越界"}]},
    ],
)
def test_invalid_llm_output_raises_rerank_error(payload):
    reranker = LLMReranker(call=lambda *_args, **_kwargs: payload)

    with pytest.raises(RerankError):
        reranker.rerank("雨中告别", [chapter("a")], time_budget_seconds=30)


def test_identity_reranker_preserves_order_without_mutating_candidates():
    candidates = [chapter("a"), chapter("b")]

    ranked = IdentityReranker().rerank(
        "雨中告别",
        candidates,
        time_budget_seconds=30,
    )

    assert [result.result_id for result in ranked] == ["a", "b"]
    assert ranked[0] is not candidates[0]
