"""按版本顺序执行可重复的 PostgreSQL 迁移。"""

import os
from pathlib import Path

import psycopg2

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class MigrationError(RuntimeError):
    """数据库迁移初始化或单个版本执行失败。"""


def _migration_version(path: Path) -> str:
    return path.name.split("_", 1)[0]


def run_migrations(
    database_url: str | None = None,
    migrations_dir: Path | None = None,
) -> list[str]:
    """执行未记录的 SQL 文件并返回本次应用版本。"""
    dsn = database_url or os.getenv("DATABASE_URL")
    if not dsn:
        raise MigrationError("DATABASE_URL 未配置")

    directory = migrations_dir or MIGRATIONS_DIR
    paths = sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))
    conn = psycopg2.connect(dsn)
    conn.autocommit = False

    try:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise MigrationError(f"初始化 schema_migrations 失败: {exc}") from exc

        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations")
            applied_versions = {row[0] for row in cur.fetchall()}

        applied_now: list[str] = []
        for path in paths:
            version = _migration_version(path)
            if version in applied_versions:
                continue

            sql = path.read_text(encoding="utf-8")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (version,),
                    )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise MigrationError(
                    f"迁移 {version} 执行失败（{path.name}）: {exc}"
                ) from exc

            applied_versions.add(version)
            applied_now.append(version)

        return applied_now
    finally:
        conn.close()
