"""CLI 参数、错误流和入口契约。"""

from __future__ import annotations

from pathlib import Path
import tomllib

from typer.testing import CliRunner

from novel_material.cli.main import app
from novel_material.search.models import SearchResponse, SearchTrace


runner = CliRunner()


class RecordingSearchService:
    def __init__(self):
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        return SearchResponse(query=request.query, results=[], trace=SearchTrace())


def test_invalid_search_limit_is_usage_error():
    result = runner.invoke(app, ["search", "chapter", "雨", "--limit", "0"])

    assert result.exit_code == 2
    assert "limit" in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_event_keyword_option_is_rejected():
    result = runner.invoke(app, ["search", "event", "雨", "--keyword"])

    assert result.exit_code == 2
    assert "No such option" in result.stderr


def test_semantic_alias_warns_and_maps_to_exact(monkeypatch):
    service = RecordingSearchService()
    monkeypatch.setattr(
        "novel_material.cli.search.create_default_search_service",
        lambda: service,
    )

    result = runner.invoke(app, ["search", "chapter", "雨", "--semantic"])

    assert result.exit_code == 0
    assert "--semantic 已弃用" in result.stderr
    assert service.requests[0].mode == "exact"


def test_semantic_alias_conflicts_with_explicit_quality_mode():
    result = runner.invoke(
        app,
        ["search", "chapter", "雨", "--mode", "quality", "--semantic"],
    )

    assert result.exit_code == 2
    assert "不能同时使用" in result.stderr


def test_pyproject_exposes_non_conflicting_entrypoint():
    root = Path(__file__).resolve().parents[2]
    scripts = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]

    assert scripts["nm"] == "novel_material.cli:main"
    assert scripts["novel-material"] == "novel_material.cli:main"


def test_root_help_exposes_terminal_control_options():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--quiet" in result.stdout
    assert "--no-progress" in result.stdout
    assert "--no-color" in result.stdout
