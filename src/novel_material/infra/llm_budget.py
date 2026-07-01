"""LLM 输出截断后的预算决策。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LengthRetryDecision:
    next_max_tokens: int
    diagnostic_code: str
    should_retry: bool


def budget_after_length_finish(
    *,
    current_max_tokens: int,
    stage_max_tokens: int,
    multiplier: int,
) -> LengthRetryDecision:
    """根据 length finish 决定是否扩展输出预算重试。"""
    if current_max_tokens < stage_max_tokens:
        next_tokens = min(stage_max_tokens, current_max_tokens * max(2, multiplier))
        return LengthRetryDecision(
            next_max_tokens=next_tokens,
            diagnostic_code="llm_budget_expanded",
            should_retry=True,
        )
    return LengthRetryDecision(
        next_max_tokens=stage_max_tokens,
        diagnostic_code="llm_task_split_required",
        should_retry=False,
    )


__all__ = ["LengthRetryDecision", "budget_after_length_finish"]
