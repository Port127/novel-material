"""搜索数据库测试共用替身。"""

from collections.abc import Iterable
from typing import Any


class FakeCursor:
    """记录 SQL 与参数并返回预设数据的游标替身。"""

    def __init__(self, rows: Iterable[dict[str, Any]] = ()):
        self.rows = list(rows)
        self.executions: list[tuple[str, Any]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql: str, params: Any = None) -> None:
        self.executions.append((sql, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.rows)


class FakeConnection:
    """复用单个游标的数据库连接替身。"""

    def __init__(self, rows: Iterable[dict[str, Any]] = ()):
        self.cursor_instance = FakeCursor(rows)
        self.closed = False
        self.session_options: dict[str, Any] = {}

    def cursor(self, **_kwargs) -> FakeCursor:
        return self.cursor_instance

    def set_session(self, **kwargs) -> None:
        self.session_options = kwargs

    def close(self) -> None:
        self.closed = True
