"""可插拔检索重排协议及严格 JSON 的 LLM 实现。"""

from collections.abc import Callable, Sequence
import json
from time import monotonic
from typing import Protocol

from novel_material.infra.llm import call_llm, load_config
from novel_material.prompts.prompt_loader import load_prompt
from novel_material.search.models import SearchResult


class RerankError(RuntimeError):
    """重排调用失败或返回内容不满足契约。"""


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: Sequence[SearchResult],
        *,
        time_budget_seconds: float,
    ) -> list[SearchResult]: ...


class IdentityReranker:
    """默认关闭深度重排时保留融合顺序。"""

    def rerank(
        self,
        query: str,
        candidates: Sequence[SearchResult],
        *,
        time_budget_seconds: float,
    ) -> list[SearchResult]:
        del query, time_budget_seconds
        return [candidate.model_copy(deep=True) for candidate in candidates]


class LLMReranker:
    """分批调用 LLM，并严格校验候选 ID、分数和解释。"""

    def __init__(
        self,
        *,
        call: Callable[..., dict] | None = None,
        batch_size: int = 20,
        min_budget_seconds: float = 5.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if batch_size < 1 or batch_size > 20:
            raise ValueError("batch_size 必须在 1 到 20 之间")
        self._call = call or _default_call
        self._batch_size = batch_size
        self._min_budget_seconds = min_budget_seconds
        self._clock = clock
        self._system_prompt = load_prompt("rerank").system_prompt

    def rerank(
        self,
        query: str,
        candidates: Sequence[SearchResult],
        *,
        time_budget_seconds: float,
    ) -> list[SearchResult]:
        if not candidates:
            return []
        started_at = self._clock()
        ranked: list[SearchResult] = []

        for offset in range(0, len(candidates), self._batch_size):
            remaining = time_budget_seconds - (self._clock() - started_at)
            if remaining < self._min_budget_seconds:
                return IdentityReranker().rerank(
                    query,
                    candidates,
                    time_budget_seconds=remaining,
                )
            batch = list(candidates[offset:offset + self._batch_size])
            try:
                payload = self._call(
                    self._system_prompt,
                    _user_prompt(query, batch),
                    remaining,
                )
            except Exception as exc:
                raise RerankError(f"LLM 重排调用失败：{exc}") from exc
            rankings = _validate_rankings(payload, batch)
            by_id = {candidate.result_id: candidate for candidate in batch}
            for ranking in rankings:
                result = by_id[ranking["result_id"]].model_copy(deep=True)
                result.scores["rerank"] = ranking["score"]
                result.final_score = ranking["score"]
                result.rank_reason = ranking["reason"]
                ranked.append(result)

        return sorted(
            ranked,
            key=lambda result: (-(result.final_score or 0.0), result.result_id),
        )


def _user_prompt(query: str, candidates: Sequence[SearchResult]) -> str:
    payload = {
        "query": query,
        "candidates": [
            {
                "result_id": result.result_id,
                "title": result.title,
                "summary": result.summary,
                "key_event": result.metadata.get("key_event"),
                "plot_progress": result.metadata.get("plot_progress"),
                "functions": result.metadata.get("chapter_functions", []),
                "emotion": result.metadata.get("emotional_tone", []),
                "scene": result.metadata.get("scene_type", []),
                "technique": result.metadata.get("technique", []),
                "neighbors": (
                    result.neighbors.model_dump(mode="json")
                    if result.neighbors is not None
                    else None
                ),
            }
            for result in candidates
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _validate_rankings(
    payload: object,
    candidates: Sequence[SearchResult],
) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("rankings"), list):
        raise RerankError("LLM 重排输出缺少 rankings 数组")
    rankings = payload["rankings"]
    expected_ids = {candidate.result_id for candidate in candidates}
    returned_ids: list[str] = []
    normalized: list[dict] = []
    for item in rankings:
        if not isinstance(item, dict):
            raise RerankError("LLM 重排条目必须是对象")
        result_id = item.get("result_id")
        score = item.get("score")
        reason = item.get("reason")
        if result_id not in expected_ids or result_id in returned_ids:
            raise RerankError("LLM 重排包含未知或重复 result_id")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1:
            raise RerankError("LLM 重排 score 必须在 0 到 1 之间")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 50:
            raise RerankError("LLM 重排 reason 必须为不超过 50 字的非空文本")
        returned_ids.append(result_id)
        normalized.append({
            "result_id": result_id,
            "score": float(score),
            "reason": reason.strip(),
        })
    if set(returned_ids) != expected_ids or len(returned_ids) != len(expected_ids):
        raise RerankError("LLM 重排必须覆盖全部候选 result_id")
    return normalized


def _default_call(system_prompt: str, user_prompt: str, timeout_seconds: float) -> dict:
    return call_llm(
        system_prompt,
        user_prompt,
        load_config(),
        timeout_override=max(1, int(timeout_seconds)),
        context="搜索重排",
        temperature_override=0.0,
    )
