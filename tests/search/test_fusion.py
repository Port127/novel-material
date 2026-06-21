from novel_material.search.fusion import diversify_results, reciprocal_rank_fusion
from novel_material.search.models import SearchResult


def item(result_id: str, material_id: str, **kwargs) -> SearchResult:
    return SearchResult(
        result_id=result_id,
        document_type="chapter",
        material_id=material_id,
        **kwargs,
    )


def test_rrf_rewards_results_found_by_multiple_retrievers():
    a, b, c = item("a", "n1"), item("b", "n2"), item("c", "n3")

    fused = reciprocal_rank_fusion(
        {"lexical": [a, b], "semantic": [c, a]},
        k=60,
    )

    assert fused[0].result_id == "a"
    assert set(fused[0].scores) >= {"lexical_rrf", "semantic_rrf"}
    assert fused[0].final_score == sum(
        score for name, score in fused[0].scores.items() if name.endswith("_rrf")
    )


def test_rrf_merges_duplicate_result_fields_without_mutating_input():
    lexical = item(
        "a",
        "n1",
        metadata={"genre": "玄幻"},
        matched_fields=["title"],
        scores={"lexical": 0.8},
    )
    semantic = item(
        "a",
        "n1",
        metadata={"theme": "成长"},
        matched_fields=["summary", "title"],
        scores={"semantic": 0.9},
    )

    fused = reciprocal_rank_fusion(
        {"lexical": [lexical], "semantic": [semantic]},
        k=60,
    )

    assert fused[0].metadata == {"genre": "玄幻", "theme": "成长"}
    assert fused[0].matched_fields == ["title", "summary"]
    assert fused[0].scores["lexical"] == 0.8
    assert fused[0].scores["semantic"] == 0.9
    assert "semantic" not in lexical.scores


def test_rrf_uses_result_id_as_stable_tie_breaker():
    fused = reciprocal_rank_fusion(
        {"lexical": [item("b", "n2")], "semantic": [item("a", "n1")]},
        k=60,
    )

    assert [result.result_id for result in fused] == ["a", "b"]


def test_diversity_fills_limit_after_capped_first_pass():
    results = [item(f"a{i}", "n1") for i in range(5)] + [
        item("b", "n2"),
        item("c", "n3"),
    ]

    diverse = diversify_results(results, limit=5, per_material_limit=2)

    assert sum(result.material_id == "n1" for result in diverse) == 3
    assert len(diverse) == 5


def test_diversity_keeps_cap_when_other_materials_are_available():
    results = [item(f"a{i}", "n1") for i in range(5)] + [
        item("b", "n2"),
        item("c", "n3"),
        item("d", "n4"),
    ]

    diverse = diversify_results(results, limit=5, per_material_limit=2)

    assert sum(result.material_id == "n1" for result in diverse) == 2
    assert len(diverse) == 5


def test_diversity_can_be_disabled_for_material_filter():
    results = [item(f"a{i}", "n1") for i in range(4)]

    diverse = diversify_results(
        results,
        limit=3,
        per_material_limit=1,
        material_id="n1",
    )

    assert [result.result_id for result in diverse] == ["a0", "a1", "a2"]
