"""中文词法索引迁移与运行器测试。"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from novel_material.cli.main import app
from novel_material.storage.migrate import MigrationError, run_migrations

runner = CliRunner()


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.connection.executions.append((sql, params))
        if "SELECT version FROM schema_migrations" in sql:
            self.rows = [(version,) for version in sorted(self.connection.applied)]
        elif "INSERT INTO schema_migrations" in sql:
            self.connection.pending_version = params[0]
        elif "BROKEN" in sql:
            raise RuntimeError("bad migration")

    def fetchall(self):
        return list(self.rows)


class FakeConnection:
    def __init__(self, applied=()):
        self.applied = set(applied)
        self.pending_version = None
        self.executions = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1
        if self.pending_version:
            self.applied.add(self.pending_version)
            self.pending_version = None

    def rollback(self):
        self.rollbacks += 1
        self.pending_version = None

    def close(self):
        self.closed = True


def test_search_migration_covers_all_entities_without_changing_vectors():
    """003 迁移应添加词法索引且不修改向量列。"""
    path = Path(
        "src/novel_material/storage/migrations/003_add_search_documents.sql"
    )
    sql = path.read_text(encoding="utf-8")

    for table in (
        "novels",
        "chapters",
        "characters",
        "worldbuilding_entities",
        "outline_sequences",
        "outline_beats",
    ):
        assert f"ALTER TABLE {table}" in sql
    assert sql.count("ADD COLUMN IF NOT EXISTS search_tokens") == 6
    assert sql.count("GENERATED ALWAYS AS") == 6
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql
    assert "DROP COLUMN" not in sql
    assert "vector(4096)" not in sql


def test_run_migrations_skips_applied_versions_and_records_new_one(
    monkeypatch,
    tmp_path,
):
    """运行器应按版本跳过已应用迁移并记录新版本。"""
    (tmp_path / "001_old.sql").write_text("OLD", encoding="utf-8")
    (tmp_path / "003_new.sql").write_text("NEW", encoding="utf-8")
    fake = FakeConnection(applied={"001"})
    monkeypatch.setattr("psycopg2.connect", lambda *_args, **_kwargs: fake)

    applied = run_migrations(
        database_url="postgresql://test",
        migrations_dir=tmp_path,
    )

    executed_sql = "\n".join(sql for sql, _params in fake.executions)
    assert applied == ["003"]
    assert "OLD" not in executed_sql
    assert "NEW" in executed_sql
    assert fake.applied == {"001", "003"}
    assert fake.closed is True


def test_run_migrations_rolls_back_failed_file(monkeypatch, tmp_path):
    """单个迁移失败时必须回滚并报告文件版本。"""
    (tmp_path / "003_bad.sql").write_text("BROKEN", encoding="utf-8")
    fake = FakeConnection()
    monkeypatch.setattr("psycopg2.connect", lambda *_args, **_kwargs: fake)

    with pytest.raises(MigrationError, match="003"):
        run_migrations(
            database_url="postgresql://test",
            migrations_dir=tmp_path,
        )

    assert fake.rollbacks == 1
    assert fake.closed is True


def test_schema_includes_search_documents_for_new_database():
    """全新数据库无需再补 003 迁移。"""
    sql = Path("src/novel_material/storage/schema.sql").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql
    assert sql.count("search_tokens TEXT NOT NULL DEFAULT ''") == 6
    assert sql.count("GENERATED ALWAYS AS") == 6
    assert "idx_chapters_search_document" in sql
    assert "idx_worldbuilding_name_trgm" in sql


@pytest.mark.parametrize(
    ("versions", "expected"),
    [(["001", "002", "003"], "已应用迁移: 001, 002, 003"), ([], "无待执行迁移")],
)
def test_storage_migrate_command_reports_result(monkeypatch, versions, expected):
    """CLI 应明确报告本次迁移状态。"""
    monkeypatch.setattr(
        "novel_material.cli.storage.run_migrations",
        lambda: versions,
    )

    result = runner.invoke(app, ["storage", "migrate"])

    assert result.exit_code == 0
    assert expected in result.stdout
