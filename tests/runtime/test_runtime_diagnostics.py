"""旧 logger 迁移适配器测试。"""

from __future__ import annotations

from novel_material.runtime.context import run_context
from novel_material.runtime.diagnostics import get_runtime_logger
from novel_material.runtime.dispatcher import RuntimeDispatcher
from novel_material.runtime.testing import MemoryEventSink


def test_runtime_logger_publishes_contextual_diagnostic():
    sink = MemoryEventSink()
    logger = get_runtime_logger("pipeline", RuntimeDispatcher([sink]))

    with run_context(command="pipeline analyze", material_id="nm_demo"):
        logger.warning("数据库不可达", code="database_unreachable")

    diagnostic = sink.events[-1]
    assert diagnostic.event_name == "DiagnosticRaised"
    assert diagnostic.component == "pipeline"
    assert diagnostic.material_id == "nm_demo"
    assert diagnostic.attributes["diagnostic_code"] == "database_unreachable"


def test_runtime_logger_without_context_has_no_side_effect(capsys):
    sink = MemoryEventSink()
    logger = get_runtime_logger("library", RuntimeDispatcher([sink]))

    logger.info("普通库消息")

    assert sink.events == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
