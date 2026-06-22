"""stdout/stderr 边界清晰的终端 Reporter。"""

from __future__ import annotations

import json

from rich.console import Console
from rich.text import Text

from novel_material.runtime.contracts import Diagnostic, RunResult

from .modes import TerminalMode


class TerminalReporter:
    def __init__(self, streams, *, mode: TerminalMode, no_color: bool = False):
        self.streams = streams
        self.mode = mode
        self.stdout = Console(
            file=streams.stdout,
            force_terminal=False,
            color_system=None,
            markup=False,
        )
        self.stderr = Console(
            file=streams.stderr,
            force_terminal=mode is TerminalMode.TTY and not no_color,
            color_system=None if no_color or mode is not TerminalMode.TTY else "auto",
            markup=False,
        )

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        self.stderr.print(Text(f"{diagnostic.code}: {diagnostic.message}"))

    def complete(self, result: RunResult) -> None:
        if self.mode is TerminalMode.JSON:
            self.streams.stdout.write(
                json.dumps(result.model_dump(mode="json"), ensure_ascii=False) + "\n"
            )
            return
        if self.mode is TerminalMode.QUIET and result.exit_code == 0:
            return
        target = self.stdout if result.exit_code == 0 else self.stderr
        target.print(Text(f"{result.status.value}: {result.command}"))

    def progress(self, *, description: str, completed: int, total: int) -> None:
        if self.mode in {TerminalMode.JSON, TerminalMode.QUIET}:
            return
        self.stderr.print(Text(f"{description} | {completed}/{total}"))

    def result_row(self, *, title: str, summary: str) -> None:
        if self.mode is TerminalMode.QUIET:
            return
        self.stderr.print(Text(f"{title} | {summary}"))


__all__ = ["TerminalReporter"]
