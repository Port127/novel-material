"""LLM 请求级 telemetry 回归测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from novel_material.infra.llm import (
    call_llm,
    get_call_details,
    start_llm_telemetry,
)
from novel_material.runtime.context import run_context
from novel_material.runtime.dispatcher import RuntimeDispatcher
from novel_material.runtime.testing import MemoryEventSink


def config() -> dict:
    return {
        "llm": {
            "api_key": "test-key",
            "base_url": "https://example.invalid",
            "model": "test-model",
            "max_tokens": 100,
            "other_timeout": 1,
            "temperature": 0.3,
        }
    }


def response(request_id: str, *, reasoning_tokens: int = 0):
    usage = SimpleNamespace(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens),
    )
    choice = SimpleNamespace(
        finish_reason="stop",
        message=SimpleNamespace(content='{"ok": true}'),
    )
    return SimpleNamespace(id=request_id, usage=usage, choices=[choice])


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes = outcomes

    def create(self, **_kwargs):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def install_fake_openai(monkeypatch, outcomes):
    completions = FakeCompletions(outcomes)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr("openai.OpenAI", lambda **_kwargs: fake_client)


def test_failed_request_does_not_reuse_previous_provider_request_id(monkeypatch):
    install_fake_openai(
        monkeypatch,
        [response("provider-success"), TimeoutError("timeout")],
    )
    sink = MemoryEventSink()
    dispatcher = RuntimeDispatcher([sink])

    with run_context(command="pipeline analyze"):
        call_llm("system", "first", config(), dispatcher=dispatcher)
        with pytest.raises(TimeoutError):
            call_llm("system", "second", config(), dispatcher=dispatcher)

    failure = [event for event in sink.events if event.event_name == "DiagnosticRaised"][-1]
    assert failure.request_id.startswith("req_")
    assert failure.provider_request_id is None
    assert "provider-success" not in failure.model_dump_json()


def test_disabled_thinking_does_not_emit_low_thinking_warning(monkeypatch):
    install_fake_openai(monkeypatch, [response("provider-1", reasoning_tokens=100)])
    sink = MemoryEventSink()

    with run_context(command="pipeline analyze"):
        call_llm(
            "system",
            "prompt",
            config(),
            thinking_budget=None,
            dispatcher=RuntimeDispatcher([sink]),
        )

    diagnostics = [
        event for event in sink.events
        if event.event_name == "DiagnosticRaised"
        and event.attributes.get("diagnostic_code") == "thinking_tokens_below_threshold"
    ]
    assert diagnostics == []
    completed = [event for event in sink.events if event.event_name == "OperationCompleted"][-1]
    assert completed.attributes["thinking_requested"] is False
    assert completed.attributes["reasoning_tokens_observed"] == 100


def test_legacy_call_detail_accessor_warns_about_deprecation():
    with pytest.warns(DeprecationWarning, match="RunSummaryAccumulator"):
        get_call_details()


def test_explicit_telemetry_collector_receives_request_result(monkeypatch):
    install_fake_openai(monkeypatch, [response("provider-explicit")])

    with run_context(command="pipeline analyze"):
        telemetry = start_llm_telemetry()
        call_llm("system", "prompt", config())

    assert telemetry.calls == 1
    assert telemetry.tokens_total == 15
    assert telemetry.details[-1]["finish_reason"] == "stop"
    assert telemetry.details[-1]["request_id"] == "provider-explicit"
