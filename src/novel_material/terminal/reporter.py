"""stdout/stderr 边界清晰的终端 Reporter。"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.text import Text

from novel_material.reporting.models import PipelineRunReport
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

    def complete_report(self, report: PipelineRunReport, path: Path) -> None:
        """输出运行状态、质量风险和报告位置的稳定摘要。"""
        if self.mode is TerminalMode.JSON:
            self.streams.stdout.write(
                json.dumps(
                    report.model_dump(mode="json"),
                    ensure_ascii=False,
                )
                + "\n"
            )
            return
        if self.mode is TerminalMode.QUIET and report.status.value == "success":
            return

        target = self.stdout if report.status.value == "success" else self.stderr
        summary = report.artifact_quality.summary
        target.print(Text(f"状态: {report.status.value}"))
        target.print(Text(f"总耗时: {report.duration_ms / 1000:.2f} 秒"))
        target.print(
            Text(
                "产物问题: "
                f"blocker={summary.blocker}, error={summary.error}, "
                f"warning={summary.warning}, info={summary.info}"
            )
        )
        top_issue = min(
            report.artifact_quality.issues,
            key=lambda item: (
                {
                    "blocker": 0,
                    "error": 1,
                    "warning": 2,
                    "info": 3,
                }[item.severity.value],
                item.code,
            ),
            default=None,
        )
        target.print(Text(f"最高风险: {top_issue.code if top_issue else '无'}"))
        target.print(Text(f"报告路径: {path}"))
        if report.next_actions:
            target.print(Text(f"下一步: {report.next_actions[0]}"))

    def progress(self, *, description: str, completed: int, total: int) -> None:
        if self.mode in {TerminalMode.JSON, TerminalMode.QUIET}:
            return
        self.stderr.print(Text(f"{description} | {completed}/{total}"))

    def result_row(self, *, title: str, summary: str) -> None:
        if self.mode is TerminalMode.QUIET:
            return
        self.stderr.print(Text(f"{title} | {summary}"))


__all__ = ["TerminalReporter"]
