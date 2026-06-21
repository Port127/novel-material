"""确定性的搜索排序质量指标。"""

from math import log2
from collections.abc import Mapping, Sequence


def recall_at_k(
    ranked: Sequence[str],
    judgments: Mapping[str, int],
    k: int,
) -> float:
    """计算前 k 条结果覆盖的相关标注比例。"""
    relevant = {result_id for result_id, score in judgments.items() if score > 0}
    if not relevant:
        return 0.0
    retrieved = set(ranked[:k])
    return len(relevant & retrieved) / len(relevant)


def reciprocal_rank(ranked: Sequence[str], judgments: Mapping[str, int]) -> float:
    """计算首个相关结果的倒数排名。"""
    for rank, result_id in enumerate(ranked, start=1):
        if judgments.get(result_id, 0) > 0:
            return 1.0 / rank
    return 0.0


def precision_at_k(
    ranked: Sequence[str],
    judgments: Mapping[str, int],
    k: int,
) -> float:
    """计算前 k 个位置中的相关结果比例。"""
    if k <= 0:
        return 0.0
    relevant_count = sum(
        judgments.get(result_id, 0) > 0 for result_id in ranked[:k]
    )
    return relevant_count / k


def ndcg_at_k(
    ranked: Sequence[str],
    judgments: Mapping[str, int],
    k: int,
) -> float:
    """使用指数增益计算前 k 条结果的归一化折损累计增益。"""
    if k <= 0 or not judgments:
        return 0.0

    def discounted_gain(relevances: Sequence[int]) -> float:
        return sum(
            (2**relevance - 1) / log2(rank + 1)
            for rank, relevance in enumerate(relevances, start=1)
        )

    actual = [judgments.get(result_id, 0) for result_id in ranked[:k]]
    ideal = sorted(judgments.values(), reverse=True)[:k]
    ideal_gain = discounted_gain(ideal)
    if ideal_gain == 0:
        return 0.0
    return discounted_gain(actual) / ideal_gain


def evaluate_ranking(
    ranked: Sequence[str],
    judgments: Mapping[str, int],
    material_ids: Mapping[str, str],
    *,
    k: int = 10,
) -> dict[str, float | int]:
    """汇总单次查询的排序质量和素材多样性。"""
    return {
        f"recall@{k}": recall_at_k(ranked, judgments, k),
        "mrr": reciprocal_rank(ranked, judgments),
        f"precision@{k}": precision_at_k(ranked, judgments, k),
        f"ndcg@{k}": ndcg_at_k(ranked, judgments, k),
        f"distinct_materials@{k}": len({
            material_ids[result_id]
            for result_id in ranked[:k]
            if result_id in material_ids
        }),
    }
