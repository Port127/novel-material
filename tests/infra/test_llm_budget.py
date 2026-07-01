from novel_material.infra.llm_budget import budget_after_length_finish


def test_length_finish_expands_budget_with_diagnostic() -> None:
    decision = budget_after_length_finish(
        current_max_tokens=8000,
        stage_max_tokens=64000,
        multiplier=2,
    )

    assert decision.next_max_tokens == 16000
    assert decision.diagnostic_code == "llm_budget_expanded"
    assert decision.should_retry is True


def test_length_finish_requires_split_at_cap() -> None:
    decision = budget_after_length_finish(
        current_max_tokens=64000,
        stage_max_tokens=64000,
        multiplier=2,
    )

    assert decision.next_max_tokens == 64000
    assert decision.diagnostic_code == "llm_task_split_required"
    assert decision.should_retry is False
