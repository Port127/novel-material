"""基于 contextvars 的运行、阶段与请求上下文。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
import secrets
from typing import Iterator

from .dispatcher import RuntimeDispatcher


@dataclass(frozen=True)
class RuntimeContext:
    """一次运行链路中的当前关联标识。"""

    run_id: str
    command: str
    material_id: str | None
    stage_id: str | None = None
    request_id: str | None = None
    provider_request_id: str | None = None


_CURRENT: ContextVar[RuntimeContext | None] = ContextVar(
    "novel_material_runtime_context",
    default=None,
)
_CURRENT_DISPATCHER: ContextVar[RuntimeDispatcher | None] = ContextVar(
    "novel_material_runtime_dispatcher",
    default=None,
)


def new_id(prefix: str) -> str:
    """生成不包含业务数据的不透明 ID。"""
    return f"{prefix}_{secrets.token_hex(16)}"


def current_context() -> RuntimeContext | None:
    return _CURRENT.get()


def current_dispatcher() -> RuntimeDispatcher | None:
    """返回当前运行的默认事件分发器。"""
    return _CURRENT_DISPATCHER.get()


def require_context() -> RuntimeContext:
    context = current_context()
    if context is None:
        raise RuntimeError("当前没有运行上下文")
    return context


def set_context(context: RuntimeContext) -> Token[RuntimeContext | None]:
    return _CURRENT.set(context)


def reset_context(token: Token[RuntimeContext | None]) -> None:
    _CURRENT.reset(token)


@contextmanager
def run_context(
    command: str,
    material_id: str | None = None,
    *,
    run_id: str | None = None,
    dispatcher: RuntimeDispatcher | None = None,
) -> Iterator[RuntimeContext]:
    context = RuntimeContext(
        run_id=run_id or new_id("run"),
        command=command,
        material_id=material_id,
    )
    token = set_context(context)
    dispatcher_token = _CURRENT_DISPATCHER.set(dispatcher)
    try:
        yield context
    finally:
        _CURRENT_DISPATCHER.reset(dispatcher_token)
        reset_context(token)


@contextmanager
def stage_context(_name: str) -> Iterator[RuntimeContext]:
    parent = require_context()
    context = replace(
        parent,
        stage_id=new_id("stage"),
        request_id=None,
        provider_request_id=None,
    )
    token = set_context(context)
    try:
        yield context
    finally:
        reset_context(token)


@contextmanager
def request_context() -> Iterator[RuntimeContext]:
    parent = require_context()
    context = replace(
        parent,
        request_id=new_id("req"),
        provider_request_id=None,
    )
    token = set_context(context)
    try:
        yield context
    finally:
        reset_context(token)


__all__ = [
    "RuntimeContext",
    "current_context",
    "current_dispatcher",
    "new_id",
    "request_context",
    "require_context",
    "reset_context",
    "run_context",
    "set_context",
    "stage_context",
]
