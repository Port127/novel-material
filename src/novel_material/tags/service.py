"""标签变更服务与最小结构化审计。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import RunEvent, RunStatus
from novel_material.runtime.dispatcher import NullDispatcher, RuntimeDispatcher


class TagService:
    def __init__(
        self,
        *,
        connection_factory: Callable,
        dispatcher: RuntimeDispatcher | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._dispatcher = dispatcher or NullDispatcher()

    def add(
        self,
        dimension: str,
        tag: str,
        domain: str,
        *,
        group: str | None = None,
        synonym_of: str | None = None,
    ) -> int:
        return self._execute(
            operation="tags.add",
            object_id=f"{dimension}/{tag}",
            sql="""
                INSERT INTO tags (dimension, tag, domain, group_name, is_common, synonym_of)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (dimension, tag) DO UPDATE SET
                    domain = EXCLUDED.domain,
                    group_name = EXCLUDED.group_name,
                    is_common = EXCLUDED.is_common,
                    synonym_of = EXCLUDED.synonym_of
            """,
            params=[dimension, tag, domain, group, domain == "common", synonym_of],
        )

    def remove(self, dimension: str, tag: str) -> int:
        return self._execute(
            operation="tags.remove",
            object_id=f"{dimension}/{tag}",
            sql="DELETE FROM tags WHERE dimension = %s AND tag = %s",
            params=[dimension, tag],
        )

    def move(self, dimension: str, tag: str, new_domain: str) -> int:
        return self._execute(
            operation="tags.move",
            object_id=f"{dimension}/{tag}",
            sql="""
                UPDATE tags SET domain = %s, is_common = %s
                WHERE dimension = %s AND tag = %s
            """,
            params=[new_domain, new_domain == "common", dimension, tag],
        )

    def set_synonym(self, dimension: str, tag: str, standard_tag: str) -> int:
        return self._execute(
            operation="tags.set_synonym",
            object_id=f"{dimension}/{tag}",
            sql="""
                UPDATE tags SET synonym_of = %s
                WHERE dimension = %s AND tag = %s
            """,
            params=[standard_tag, dimension, tag],
        )

    def _execute(
        self,
        *,
        operation: str,
        object_id: str,
        sql: str,
        params: list,
    ) -> int:
        self._emit(operation, object_id, phase="started")
        connection = self._connection_factory()
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                affected = cursor.rowcount
        except Exception:
            self._emit(operation, object_id, phase="failed", status=RunStatus.FAILED)
            raise
        finally:
            connection.close()
        self._emit(
            operation,
            object_id,
            phase="completed",
            status=RunStatus.SUCCESS,
            affected_rows=affected,
        )
        return affected

    def _emit(
        self,
        operation: str,
        object_id: str,
        *,
        phase: str,
        status: RunStatus | None = None,
        affected_rows: int | None = None,
    ) -> None:
        context = current_context()
        if context is None:
            return
        now = datetime.now(timezone.utc)
        attributes = {
            "phase": phase,
            "object_type": "tag",
            "object_id": object_id,
        }
        if affected_rows is not None:
            attributes["affected_rows"] = affected_rows
        self._dispatcher.emit(
            RunEvent(
                event_name="AuditRecorded",
                event_id=new_id("event"),
                occurred_at=now,
                observed_at=now,
                run_id=context.run_id,
                stage_id=context.stage_id,
                command=context.command,
                component="tags",
                operation=operation,
                status=status,
                attributes=attributes,
            )
        )


__all__ = ["TagService"]
