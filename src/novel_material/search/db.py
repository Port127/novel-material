"""搜索模块共用的只读 PostgreSQL 边界。"""

from contextlib import contextmanager
import os

import psycopg2


class SearchDatabaseError(RuntimeError):
    """搜索数据库配置或连接失败。"""


@contextmanager
def readonly_connection(database_url: str | None = None):
    """创建并在退出时关闭只读、自动提交的数据库连接。"""
    dsn = database_url or os.getenv("DATABASE_URL")
    if not dsn:
        raise SearchDatabaseError("DATABASE_URL 未配置")

    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        conn.set_session(readonly=True, autocommit=True)
    except psycopg2.Error as exc:
        raise SearchDatabaseError(f"数据库连接失败: {exc}") from exc

    try:
        yield conn
    finally:
        conn.close()
