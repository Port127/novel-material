"""终端输出模式解析。"""

from __future__ import annotations

from enum import Enum


class TerminalMode(str, Enum):
    TTY = "tty"
    PLAIN = "plain"
    JSON = "json"
    QUIET = "quiet"


def resolve_mode(
    *,
    json_output: bool,
    quiet: bool,
    no_progress: bool,
    is_tty: bool,
) -> TerminalMode:
    if json_output:
        return TerminalMode.JSON
    if quiet:
        return TerminalMode.QUIET
    if no_progress or not is_tty:
        return TerminalMode.PLAIN
    return TerminalMode.TTY


__all__ = ["TerminalMode", "resolve_mode"]
