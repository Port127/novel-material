"""搜索排序指标测试。"""

from novel_material.eval.search_metrics import evaluate_ranking


def test_evaluate_ranking_computes_recall_mrr_ndcg_precision_and_diversity():
    """一次评测应返回质量与多样性指标。"""
    ranked = ["a", "b", "c", "d"]
    judgments = {"a": 3, "c": 2, "x": 1}
    material_ids = {"a": "n1", "b": "n1", "c": "n2", "d": "n3"}

    metrics = evaluate_ranking(ranked, judgments, material_ids, k=4)

    assert metrics["recall@4"] == 2 / 3
    assert metrics["mrr"] == 1.0
    assert metrics["precision@4"] == 0.5
    assert 0 < metrics["ndcg@4"] <= 1
    assert metrics["distinct_materials@4"] == 3


def test_evaluate_ranking_returns_zero_for_empty_inputs():
    """空排名和空标注不应触发除零。"""
    metrics = evaluate_ranking([], {}, {}, k=10)

    assert metrics == {
        "recall@10": 0.0,
        "mrr": 0.0,
        "precision@10": 0.0,
        "ndcg@10": 0.0,
        "distinct_materials@10": 0,
    }
