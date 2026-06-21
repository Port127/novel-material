"""搜索评测 CLI 工作流测试。"""

from pathlib import Path

from typer.testing import CliRunner
import yaml

from novel_material.cli.main import app
from novel_material.search.models import SearchResult

runner = CliRunner()


def _query_file(
    path: Path,
    filters: dict | None = None,
    *,
    query: str = "开局困境",
    document_type: str = "chapter",
) -> None:
    path.write_text(
        yaml.safe_dump([{
            "id": "chapter_001",
            "query": query,
            "document_type": document_type,
            "filters": filters or {},
            "judgments": {},
            "require_diversity": True,
            "require_neighbors": True,
        }], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_eval_search_help_exposes_labeling_workflow():
    """评测 CLI 应显式展示准备、导入标签和评分三个步骤。"""
    result = runner.invoke(app, ["eval", "search", "--help"])

    assert result.exit_code == 0
    assert all(name in result.stdout for name in ("prepare", "import-labels", "score"))


def test_eval_prepare_exports_candidates(monkeypatch, tmp_path):
    """prepare 应通过文档类型调度器导出候选。"""
    queries = tmp_path / "queries.yaml"
    output = tmp_path / "candidates.yaml"
    _query_file(queries, {"chapter_num": 1})
    observed_filters = []

    def fake_search(case, _limit, _mode):
        observed_filters.append(case.filters)
        if case.filters:
            return []
        return [SearchResult(
            result_id="chapter:nm_demo:1",
            document_type="chapter",
            material_id="nm_demo",
            title="开篇",
            summary="主角陷入困境。",
        )]

    monkeypatch.setattr("novel_material.cli.eval._search_case", fake_search)

    result = runner.invoke(app, [
        "eval", "search", "prepare",
        "--queries", str(queries),
        "--output", str(output),
    ])

    assert result.exit_code == 0
    assert observed_filters == [{"chapter_num": 1}, {}]
    row = yaml.safe_load(output.read_text(encoding="utf-8"))[0]
    assert row["relevance"] is None
    assert row["candidate_source"] == "relaxed"


def test_eval_score_rejects_unlabeled_queries(tmp_path):
    """score 遇到空 judgments 时必须非零退出且不写报告。"""
    queries = tmp_path / "queries.yaml"
    output = tmp_path / "report.json"
    _query_file(queries)

    result = runner.invoke(app, [
        "eval", "search", "score",
        "--queries", str(queries),
        "--output", str(output),
    ])

    assert result.exit_code == 1
    assert "chapter_001" in result.stdout
    assert not output.exists()


def test_eval_prepare_uses_inventory_only_after_detail_searches_are_empty(
    monkeypatch,
    tmp_path,
):
    """detail 前两路为空时才使用无关键词库存。"""
    queries = tmp_path / "queries.yaml"
    output = tmp_path / "candidates.yaml"
    _query_file(
        queries,
        query="感情线节拍",
        document_type="detail",
    )
    observed = []

    def fake_search(case, _limit, _mode):
        observed.append((case.query, case.filters))
        if case.query:
            return []
        return [SearchResult(
            result_id="detail:nm_demo:1:1",
            document_type="detail",
            material_id="nm_demo",
            title="关系推进",
            summary="人物关系发生变化。",
        )]

    monkeypatch.setattr("novel_material.cli.eval._search_case", fake_search)

    result = runner.invoke(app, [
        "eval", "search", "prepare",
        "--queries", str(queries),
        "--output", str(output),
        "--limit", "1",
    ])

    assert result.exit_code == 0
    assert observed == [
        ("感情线节拍", {}),
        ("感情线节拍", {}),
        ("", {}),
    ]
    row = yaml.safe_load(output.read_text(encoding="utf-8"))[0]
    assert row["candidate_source"] == "inventory"
