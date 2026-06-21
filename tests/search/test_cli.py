"""搜索 CLI 的稳定输出与错误语义测试。"""

import json

from typer.testing import CliRunner

from novel_material.cli.main import app
from novel_material.search.models import SearchResponse, SearchResult, SearchTrace

runner = CliRunner()


class FakeSearchService:
    def __init__(self, results=None):
        self.requests = []
        self.results = results or []

    def search(self, request):
        self.requests.append(request)
        return SearchResponse(
            query=request.query,
            results=self.results,
            trace=SearchTrace(stages=["lexical", "semantic", "fusion"]),
        )


def test_chapter_json_is_machine_readable(monkeypatch):
    """JSON 模式只输出可解析的统一响应。"""
    service = FakeSearchService(results=[SearchResult(
            result_id="chapter:nm_demo:1",
            document_type="chapter",
            material_id="nm_demo",
            chapter=1,
            title="开篇",
            summary="主角陷入困境。",
        )])
    monkeypatch.setattr(
        "novel_material.cli.search.create_default_search_service",
        lambda: service,
    )

    result = runner.invoke(app, ["search", "chapter", "开局困境", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["results"][0]["result_id"] == "chapter:nm_demo:1"
    assert payload["trace"]["stages"] == ["lexical", "semantic", "fusion"]
    assert service.requests[0].document_types == ["chapter"]
    assert service.requests[0].mode == "quality"


def test_search_help_exposes_all_document_types():
    """搜索帮助应列出全部七类公开命令。"""
    result = runner.invoke(app, ["search", "--help"])

    assert result.exit_code == 0
    assert all(
        name in result.stdout
        for name in ("chapter", "event", "outline", "character", "world", "detail", "insight")
    )


def test_filter_only_command_builds_nonempty_search_request(monkeypatch):
    service = FakeSearchService()
    monkeypatch.setattr(
        "novel_material.cli.search.create_default_search_service",
        lambda: service,
    )

    result = runner.invoke(
        app,
        ["search", "character", "--archetype", "导师", "--json"],
    )

    assert result.exit_code == 0
    assert service.requests[0].query == "导师"
    assert service.requests[0].filters == {"archetype": "导师"}


def test_cli_forwards_quality_control_options(monkeypatch):
    service = FakeSearchService()
    monkeypatch.setattr(
        "novel_material.cli.search.create_default_search_service",
        lambda: service,
    )

    result = runner.invoke(app, [
        "search", "chapter", "雨中告别", "--mode", "exact",
        "--candidate-limit", "25", "--time-budget", "30", "--json",
    ])

    assert result.exit_code == 0
    request = service.requests[0]
    assert request.mode == "exact"
    assert request.candidate_limit == 25
    assert request.time_budget_seconds == 30


def test_database_failure_exits_nonzero(monkeypatch):
    """数据库故障不得被误报为没有匹配结果。"""
    class FailingService:
        def search(self, _request):
            raise RuntimeError("数据库连接失败")

    monkeypatch.setattr(
        "novel_material.cli.search.create_default_search_service",
        FailingService,
    )

    result = runner.invoke(app, ["search", "chapter", "开局困境"])

    assert result.exit_code == 1
    assert "数据库连接失败" in result.stdout
    assert "未找到" not in result.stdout
