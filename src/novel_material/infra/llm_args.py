"""LLM 调用参数封装。

核心功能：
- LLMCallArgs: 封装 call_llm 的多个参数为对象

用于简化函数调用，提高可读性。
"""

from dataclasses import dataclass


@dataclass
class LLMCallArgs:
    """LLM 调用参数封装。"""
    system_prompt: str
    user_prompt: str
    config: dict
    max_tokens_override: int | None = None
    timeout_override: int | None = None
    context: str | None = None
    thinking_budget: int | None = None
    temperature_override: float | None = None


__all__ = ["LLMCallArgs"]