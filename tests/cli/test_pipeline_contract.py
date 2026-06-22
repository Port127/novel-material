"""Pipeline CLI 的结果和退出码契约。"""

from __future__ import annotations

from typer.testing import CliRunner
import pytest

from novel_material.cli.main import app
from novel_material.runtime.contracts import RunStatus, StageResult


runner = CliRunner()


def failed_stage(name: str) -> StageResult:
    return StageResult(stage_id=f"stage-{name}", name=name, status=RunStatus.FAILED)


def test_ingest_failure_exits_one(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_ingest_stage",
        lambda *_args, **_kwargs: failed_stage("ingest"),
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", "ingest", "missing.txt"])

    assert result.exit_code == 1
    assert "入库失败" in result.stderr
    assert "入库成功" not in result.stdout


def test_outline_failure_exits_one(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.run_outline_stage",
        lambda *_args, **_kwargs: failed_stage("outline"),
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", "outline", "nm_demo"])

    assert result.exit_code == 1
    assert "大纲生成失败" in result.stderr
    assert "大纲生成完成" not in result.stdout


def test_missing_material_status_is_not_complete(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.pipeline.get_pipeline_progress",
        lambda _material_id: {"exists": False},
    )

    result = runner.invoke(app, ["pipeline", "status", "nm_missing"])

    assert result.exit_code == 1
    assert "素材目录不存在" in result.stderr
    assert "流水线已完成" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("command", "entrypoint", "message"),
    [
        ("worldbuilding", "run_worldbuilding_stage", "世界观提取失败"),
        ("characters", "run_characters_stage", "人物提取失败"),
        ("tags", "run_tags_stage", "标签生成失败"),
        ("refine", "run_refine_stage", "精调失败"),
    ],
)
def test_remaining_single_stage_failures_exit_one(
    monkeypatch,
    command,
    entrypoint,
    message,
):
    monkeypatch.setattr(
        f"novel_material.cli.pipeline.{entrypoint}",
        lambda *_args, **_kwargs: failed_stage(command),
        raising=False,
    )

    result = runner.invoke(app, ["pipeline", command, "nm_demo"])

    assert result.exit_code == 1
    assert message in result.stderr
    assert "完成" not in result.stdout
