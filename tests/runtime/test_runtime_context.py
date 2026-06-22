"""运行上下文隔离测试。"""

from __future__ import annotations

import pytest

from novel_material.runtime.context import (
    current_context,
    request_context,
    run_context,
    stage_context,
)


def test_nested_context_restores_parent_stage():
    assert current_context() is None
    with run_context(command="pipeline full", material_id="nm_demo") as run:
        assert run.run_id.startswith("run_")
        with stage_context("analyze") as stage:
            assert current_context() == stage
            assert stage.stage_id.startswith("stage_")
        assert current_context().stage_id is None
        assert current_context().run_id == run.run_id
    assert current_context() is None


def test_request_context_uses_new_internal_id_and_restores_stage():
    with run_context(command="pipeline analyze"):
        with stage_context("analyze") as stage:
            with request_context() as request:
                assert request.request_id.startswith("req_")
                assert request.provider_request_id is None
            assert current_context() == stage


def test_context_is_restored_after_exception():
    with pytest.raises(RuntimeError, match="boom"):
        with run_context(command="pipeline analyze"):
            raise RuntimeError("boom")
    assert current_context() is None

