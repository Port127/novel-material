"""搜索 CLI 的稳定输出与错误语义测试。"""

import json

from typer.testing import CliRunner

from novel_material.cli.main import app
from novel_material.search.models import SearchResult

runner = CliRunner()


def test_chapter_json_is_machine_readable(monkeypatch):
    """JSON 模式只输出可解析的统一响应。"""
    monkeypatch.setattr(
        "novel_material.cli.search.search_chapters",
        lambda **_kwargs: [SearchResult(
            result_id="chapter:nm_demo:1",
            document_type="chapter",
            material_id="nm_demo",
            chapter=1,
            title="开篇",
            summary="主角陷入困境。",
        )],
    )

    result = runner.invoke(app, ["search", "chapter", "开局困境", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["results"][0]["result_id"] == "chapter:nm_demo:1"


def test_search_help_exposes_all_document_types():
    """搜索帮助应列出全部七类公开命令。"""
    result = runner.invoke(app, ["search", "--help"])

    assert result.exit_code == 0
    assert all(
        name in result.stdout
        for name in ("chapter", "event", "outline", "character", "world", "detail", "insight")
    )


def test_database_failure_exits_nonzero(monkeypatch):
    """数据库故障不得被误报为没有匹配结果。"""
    monkeypatch.setattr(
        "novel_material.cli.search.search_chapters",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("数据库连接失败")),
    )

    result = runner.invoke(app, ["search", "chapter", "开局困境"])

    assert result.exit_code == 1
    assert "数据库连接失败" in result.stdout
    assert "未找到" not in result.stdout
