"""数据变更命令的结构化审计事件测试。"""

from novel_material.runtime.context import run_context
from novel_material.runtime.dispatcher import RuntimeDispatcher
from novel_material.runtime.testing import MemoryEventSink
from novel_material.tags.service import TagService
from novel_material.storage.sync_core import sync_novel
from novel_material.storage.sync_utils import SchemaValidationError
from novel_material.material.delete import delete_material
from novel_material.material.import_material import import_material
from novel_material.storage.migrate import MigrationError, run_migrations
import pytest


class FakeCursor:
    rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params


class FakeConnection:
    def __init__(self):
        self.autocommit = False
        self.closed = False

    def cursor(self):
        return FakeCursor()

    def close(self):
        self.closed = True


def test_tag_mutation_emits_started_and_completed_audit_without_payload():
    sink = MemoryEventSink()
    connection = FakeConnection()
    service = TagService(
        connection_factory=lambda: connection,
        dispatcher=RuntimeDispatcher([sink]),
    )

    with run_context(command="tags add"):
        affected = service.add("element", "宗门", "xuanhuan", group="设定")

    events = sink.events_named("AuditRecorded")
    assert affected == 1
    assert [event.attributes["phase"] for event in events] == ["started", "completed"]
    assert all(event.operation == "tags.add" for event in events)
    assert events[-1].attributes["object_id"] == "element/宗门"
    assert events[-1].attributes["affected_rows"] == 1
    assert all("sql" not in event.attributes for event in events)
    assert all("payload" not in event.attributes for event in events)
    assert connection.closed is True


def test_sync_failure_emits_minimal_audit_event(tmp_path, monkeypatch):
    material_id = "nm_demo"
    (tmp_path / material_id).mkdir()
    sink = MemoryEventSink()
    monkeypatch.setattr("novel_material.storage.sync_core.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.storage.sync_core._precheck_schema",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            SchemaValidationError("invalid")
        ),
    )

    with run_context(command="storage sync", material_id=material_id):
        result = sync_novel(
            material_id,
            dispatcher=RuntimeDispatcher([sink]),
        )

    events = sink.events_named("AuditRecorded")
    assert result.status.value == "failed"
    assert [event.attributes["phase"] for event in events] == ["started", "failed"]
    assert all(event.operation == "storage.sync" for event in events)
    assert all(set(event.attributes) <= {"phase", "object_type", "object_id"} for event in events)


def test_material_delete_and_import_failures_use_same_audit_fields(tmp_path):
    sink = MemoryEventSink()
    dispatcher = RuntimeDispatcher([sink])

    with run_context(command="material delete", material_id="nm_missing"):
        deleted = delete_material(
            "nm_missing",
            confirm=False,
            novels_dir=tmp_path,
            dispatcher=dispatcher,
        )
    with run_context(command="material import"):
        imported = import_material(
            tmp_path / "missing",
            dispatcher=dispatcher,
        )

    failed = [
        event
        for event in sink.events_named("AuditRecorded")
        if event.attributes["phase"] == "failed"
    ]
    assert deleted is False
    assert imported is None
    assert [event.operation for event in failed] == ["material.delete", "material.import"]
    assert all(set(event.attributes) == {"phase", "object_type", "object_id"} for event in failed)


def test_storage_migration_failure_is_audited(monkeypatch):
    sink = MemoryEventSink()
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with run_context(command="storage migrate"):
        with pytest.raises(MigrationError):
            run_migrations(dispatcher=RuntimeDispatcher([sink]))

    events = sink.events_named("AuditRecorded")
    assert [event.attributes["phase"] for event in events] == ["started", "failed"]
    assert all(event.operation == "storage.migrate" for event in events)
