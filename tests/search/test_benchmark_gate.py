from scripts.benchmark_search import candidate_gate, requires_large_confirmation


def test_candidate_gate_requires_recall_and_ndcg_thresholds():
    assert candidate_gate(
        candidate_recall=0.985,
        exact_ndcg=0.82,
        candidate_ndcg=0.815,
    ) is True
    assert candidate_gate(
        candidate_recall=0.97,
        exact_ndcg=0.82,
        candidate_ndcg=0.82,
    ) is False
    assert candidate_gate(
        candidate_recall=0.99,
        exact_ndcg=0.82,
        candidate_ndcg=0.80,
    ) is False


def test_candidate_gate_rejects_slow_or_query_level_regression():
    assert candidate_gate(
        candidate_recall=0.99,
        exact_ndcg=0.82,
        candidate_ndcg=0.82,
        p95_seconds=181,
    ) is False
    assert candidate_gate(
        candidate_recall=0.99,
        exact_ndcg=0.82,
        candidate_ndcg=0.82,
        lost_qualified_queries=1,
    ) is False


def test_large_benchmark_requires_explicit_confirmation():
    assert requires_large_confirmation(2_500_000) is True
    assert requires_large_confirmation(500_000) is False
