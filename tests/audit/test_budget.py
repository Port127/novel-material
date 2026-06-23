from novel_material.audit.budget import ReviewBudget
from novel_material.runtime.testing import FakeClock


def test_budget_refuses_call_that_would_cross_deadline() -> None:
    clock = FakeClock()
    budget = ReviewBudget(max_seconds=100, max_calls=2, clock=clock.monotonic)

    assert budget.reserve(estimated_seconds=60) is True
    clock.advance(50)

    assert budget.reserve(estimated_seconds=60) is False
    assert budget.stop_reason == "time_budget_exhausted"


def test_budget_refuses_calls_after_call_limit() -> None:
    budget = ReviewBudget(max_seconds=1000, max_calls=1, clock=lambda: 0)

    assert budget.reserve(estimated_seconds=10) is True
    assert budget.reserve(estimated_seconds=10) is False
    assert budget.stop_reason == "call_budget_exhausted"
    assert budget.reserve(estimated_seconds=0) is False


def test_budget_snapshot_records_elapsed_and_calls() -> None:
    clock = FakeClock(initial=10)
    budget = ReviewBudget(max_seconds=100, max_calls=2, clock=clock.monotonic)
    assert budget.reserve(estimated_seconds=20) is True
    clock.advance(12)

    usage = budget.snapshot(mode="llm_review")

    assert usage.mode == "llm_review"
    assert usage.elapsed_seconds == 12
    assert usage.calls_used == 1
    assert usage.max_calls == 2
