"""结构化运行日志消费者。"""

from .reader import RunLogReadError, read_run_events

__all__ = ["RunLogReadError", "read_run_events"]
