"""无文件、无终端副作用的旧 logger 迁移适配器。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .context import current_context, new_id
from .contracts import RunEvent
from .dispatcher import NullDispatcher, RuntimeDispatcher


_SEVERITY = {
    "DEBUG": 5,
    "INFO": 9,
    "WARNING": 13,
    "ERROR": 17,
    "CRITICAL": 21,
}


class RuntimeDiagnosticLogger:
    def __init__(
        self,
        component: str,
        dispatcher: RuntimeDispatcher | None = None,
    ) -> None:
        self.component = component
        self.dispatcher = dispatcher or NullDispatcher()

    def debug(self, message: str, *args: object, **kwargs: Any) -> None:
        self._emit("DEBUG", message, args, kwargs)

    def info(self, message: str, *args: object, **kwargs: Any) -> None:
        self._emit("INFO", message, args, kwargs)

    def warning(self, message: str, *args: object, **kwargs: Any) -> None:
        self._emit("WARNING", message, args, kwargs)

    def error(self, message: str, *args: object, **kwargs: Any) -> None:
        self._emit("ERROR", message, args, kwargs)

    def critical(self, message: str, *args: object, **kwargs: Any) -> None:
        self._emit("CRITICAL", message, args, kwargs)

    def _emit(
        self,
        severity: str,
        message: str,
        args: tuple[object, ...],
        kwargs: dict[str, Any],
    ) -> None:
        context = current_context()
        if context is None:
            return
        rendered = message % args if args else message
        code = kwargs.pop("code", "runtime_diagnostic")
        attributes = dict(kwargs.pop("attributes", {}) or {})
        attributes.update(
            {
                "diagnostic_code": code,
                "message": rendered,
            }
        )
        now = datetime.now(timezone.utc)
        self.dispatcher.emit(
            RunEvent(
                event_name="DiagnosticRaised",
                event_id=new_id("event"),
                occurred_at=now,
                observed_at=now,
                severity_text=severity,
                severity_number=_SEVERITY[severity],
                run_id=context.run_id,
                stage_id=context.stage_id,
                request_id=context.request_id,
                provider_request_id=context.provider_request_id,
                command=context.command,
                component=self.component,
                operation="diagnostic",
                material_id=context.material_id,
                attributes=attributes,
            )
        )


def get_runtime_logger(
    component: str,
    dispatcher: RuntimeDispatcher | None = None,
) -> RuntimeDiagnosticLogger:
    return RuntimeDiagnosticLogger(component, dispatcher)


__all__ = ["RuntimeDiagnosticLogger", "get_runtime_logger"]
