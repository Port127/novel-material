"""终端输出测试替身。"""

from __future__ import annotations

from io import StringIO


class RecordingTerminal:
    def __init__(self) -> None:
        self.stdout = StringIO()
        self.stderr = StringIO()

    @property
    def stdout_text(self) -> str:
        return self.stdout.getvalue()

    @property
    def stderr_text(self) -> str:
        return self.stderr.getvalue()


__all__ = ["RecordingTerminal"]
