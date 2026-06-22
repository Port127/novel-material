"""终端错误适配入口。"""

from __future__ import annotations

from novel_material.runtime.contracts import Diagnostic


def error_diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(code=code, message=message, severity="error")


__all__ = ["error_diagnostic"]
