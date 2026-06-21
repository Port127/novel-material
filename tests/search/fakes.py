"""搜索数据库测试共用替身。"""

from collections.abc import Iterable
from typing import Any


class FakeCursor:
    """记录 SQL 与参数并返回预设数据的游标替身。"""

    def __init__(
        self,
        rows: Iterable[dict[str, Any]] = (),
        result_sets: Iterable[Iterable[dict[str, Any]]] | None = None,
    ):
        self.result_sets = (
            [list(result_set) for result_set in result_sets]
            if result_sets is not None
            else [list(rows)]
        )
        self.result_index = 0
        self.executions: list[tuple[str, Any]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql: str, params: Any = None) -> None:
        self.executions.append((sql, params))

    def fetchall(self) -> list[dict[str, Any]]:
        if not self.result_sets:
            return []
        index = min(self.result_index, len(self.result_sets) - 1)
        self.result_index += 1
        return list(self.result_sets[index])


class FakeConnection:
    """复用单个游标的数据库连接替身。"""

    def __init__(
        self,
        rows: Iterable[dict[str, Any]] = (),
        result_sets: Iterable[Iterable[dict[str, Any]]] | None = None,
    ):
        self.cursor_instance = FakeCursor(rows, result_sets=result_sets)
        self.closed = False
        self.session_options: dict[str, Any] = {}

    def cursor(self, **_kwargs) -> FakeCursor:
        return self.cursor_instance

    def set_session(self, **kwargs) -> None:
        self.session_options = kwargs

    def close(self) -> None:
        self.closed = True
