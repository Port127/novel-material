"""多路检索结果的 RRF 融合与跨素材多样性控制。"""

from collections import Counter
from collections.abc import Mapping, Sequence

from novel_material.search.models import SearchResult


def reciprocal_rank_fusion(
    ranked_results: Mapping[str, Sequence[SearchResult]],
    *,
    k: int = 60,
) -> list[SearchResult]:
    """按倒数排名融合多路结果，并合并相同 ``result_id`` 的信息。"""
    if k < 0:
        raise ValueError("k 不能小于 0")

    fused: dict[str, SearchResult] = {}
    totals: Counter[str] = Counter()

    for retriever, results in ranked_results.items():
        score_name = f"{retriever}_rrf"
        seen: set[str] = set()
        for rank, result in enumerate(results, start=1):
            if result.result_id in seen:
                continue
            seen.add(result.result_id)

            contribution = 1.0 / (k + rank)
            totals[result.result_id] += contribution

            if result.result_id not in fused:
                fused[result.result_id] = result.model_copy(deep=True)
            else:
                _merge_result(fused[result.result_id], result)
            fused[result.result_id].scores[score_name] = contribution

    for result_id, result in fused.items():
        result.final_score = totals[result_id]

    return sorted(
        fused.values(),
        key=lambda result: (-(result.final_score or 0.0), result.result_id),
    )


def diversify_results(
    results: Sequence[SearchResult],
    *,
    limit: int,
    per_material_limit: int = 2,
    material_id: str | None = None,
) -> list[SearchResult]:
    """限制单一素材首轮占比，不足时再按原顺序补齐。"""
    if limit <= 0:
        return []
    if material_id is not None:
        return list(results[:limit])
    if per_material_limit < 1:
        raise ValueError("per_material_limit 必须大于 0")

    selected: list[SearchResult] = []
    skipped: list[SearchResult] = []
    counts: Counter[str] = Counter()

    for result in results:
        if counts[result.material_id] >= per_material_limit:
            skipped.append(result)
            continue
        selected.append(result)
        counts[result.material_id] += 1
        if len(selected) == limit:
            return selected

    selected.extend(skipped[: limit - len(selected)])
    return selected


def _merge_result(target: SearchResult, incoming: SearchResult) -> None:
    """把另一召回通道提供的补充字段合并到首个结果。"""
    target.metadata.update(incoming.metadata)
    target.scores.update(incoming.scores)
    target.matched_fields = list(
        dict.fromkeys([*target.matched_fields, *incoming.matched_fields])
    )

    for field in ("title", "summary", "content", "source", "neighbors", "rank_reason"):
        if not getattr(target, field) and getattr(incoming, field):
            setattr(target, field, getattr(incoming, field))
