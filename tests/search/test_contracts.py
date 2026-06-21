"""搜索模块的数据库边界与返回契约测试。"""

import pytest

from novel_material.search.db import SearchDatabaseError, readonly_connection
from tests.search.fakes import FakeConnection


def test_readonly_connection_reports_missing_database_url(monkeypatch):
    """缺少数据库配置时应返回明确的搜索数据库错误。"""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SearchDatabaseError, match="DATABASE_URL"):
        with readonly_connection(database_url=None):
            pass


def test_readonly_connection_closes_connection(monkeypatch):
    """只读连接退出上下文后必须关闭。"""
    fake = FakeConnection()
    monkeypatch.setattr("psycopg2.connect", lambda *_args, **_kwargs: fake)

    with readonly_connection("postgresql://test") as conn:
        assert conn is fake

    assert fake.session_options == {"readonly": True, "autocommit": True}
    assert fake.closed is True
