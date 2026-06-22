"""按版本顺序执行可重复的 PostgreSQL 迁移。"""

import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import RunEvent, RunStatus
from novel_material.runtime.dispatcher import NullDispatcher, RuntimeDispatcher

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class MigrationError(RuntimeError):
    """数据库迁移初始化或单个版本执行失败。"""


def _migration_version(path: Path) -> str:
    return path.name.split("_", 1)[0]


def _run_migrations_impl(
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


def run_migrations(
    database_url: str | None = None,
    migrations_dir: Path | None = None,
    *,
    dispatcher: RuntimeDispatcher | None = None,
) -> list[str]:
    """执行迁移，并发布不包含 SQL 内容的审计事件。"""
    event_dispatcher = dispatcher or NullDispatcher()
    _emit_migration_audit(event_dispatcher, phase="started")
    try:
        versions = _run_migrations_impl(database_url, migrations_dir)
    except Exception:
        _emit_migration_audit(
            event_dispatcher,
            phase="failed",
            status=RunStatus.FAILED,
        )
        raise
    _emit_migration_audit(
        event_dispatcher,
        phase="completed",
        status=RunStatus.SUCCESS,
    )
    return versions


def _emit_migration_audit(
    dispatcher: RuntimeDispatcher,
    *,
    phase: str,
    status: RunStatus | None = None,
) -> None:
    context = current_context()
    if context is None:
        return
    now = datetime.now(timezone.utc)
    dispatcher.emit(
        RunEvent(
            event_name="AuditRecorded",
            event_id=new_id("event"),
            occurred_at=now,
            observed_at=now,
            run_id=context.run_id,
            stage_id=context.stage_id,
            command=context.command,
            component="storage",
            operation="storage.migrate",
            status=status,
            attributes={
                "phase": phase,
                "object_type": "database_schema",
                "object_id": "schema_migrations",
            },
        )
    )
