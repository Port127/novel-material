"""Golden Query 加载、候选导出和评分测试。"""

from pathlib import Path
from collections import Counter

import pytest
import yaml

from novel_material.eval.search_eval import (
    evaluate_cases,
    export_candidates,
    import_candidate_labels,
    load_search_cases,
    validate_labeled_cases,
)
from novel_material.search.models import SearchResult


def _write_queries(path: Path, judgments: dict[str, int] | None = None) -> None:
    path.write_text(
        yaml.safe_dump(
            [{
                "id": "chapter_001",
                "query": "开局困境",
                "document_type": "chapter",
                "filters": {},
                "judgments": judgments or {},
                "require_diversity": True,
                "require_neighbors": True,
            }],
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _result(result_id: str, material_id: str = "nm_demo") -> SearchResult:
    return SearchResult(
        result_id=result_id,
        document_type="chapter",
        material_id=material_id,
        title="开篇",
        summary="主角陷入困境。",
    )


def test_validate_labeled_cases_rejects_missing_judgments(tmp_path):
    """评分前必须拒绝没有人工判断的查询。"""
    path = tmp_path / "queries.yaml"
    _write_queries(path)

    cases = load_search_cases(path)

    with pytest.raises(ValueError, match="chapter_001"):
        validate_labeled_cases(cases)


def test_export_candidates_writes_unlabeled_rows_without_changing_queries(tmp_path):
    """候选导出只写目标文件，相关性初始值必须为空。"""
    queries_path = tmp_path / "queries.yaml"
    output_path = tmp_path / "candidates.yaml"
    _write_queries(queries_path)
    original = queries_path.read_text(encoding="utf-8")

    export_candidates(
        load_search_cases(queries_path),
        lambda _case, _limit: [_result("chapter:nm_demo:1")],
        output_path,
    )

    rows = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert rows == [{
        "case_id": "chapter_001",
        "query": "开局困境",
        "result_id": "chapter:nm_demo:1",
        "material_id": "nm_demo",
        "title": "开篇",
        "summary": "主角陷入困境。",
        "relevance": None,
    }]
    assert queries_path.read_text(encoding="utf-8") == original


def test_export_candidates_keeps_case_visible_when_search_returns_no_results(tmp_path):
    """零结果查询也必须在候选文件中保留可审计记录。"""
    queries_path = tmp_path / "queries.yaml"
    output_path = tmp_path / "candidates.yaml"
    _write_queries(queries_path)

    export_candidates(
        load_search_cases(queries_path),
        lambda _case, _limit: [],
        output_path,
    )

    rows = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert rows == [{
        "case_id": "chapter_001",
        "query": "开局困境",
        "result_id": None,
        "material_id": None,
        "title": "",
        "summary": "",
        "relevance": None,
        "status": "no_candidates",
    }]


def test_import_candidate_labels_merges_scores_into_queries(tmp_path):
    """人工填写的 0～3 分应按 case 合并回查询集。"""
    queries_path = tmp_path / "queries.yaml"
    candidates_path = tmp_path / "candidates.yaml"
    _write_queries(queries_path)
    candidates_path.write_text(
        yaml.safe_dump([{
            "case_id": "chapter_001",
            "query": "开局困境",
            "result_id": "chapter:nm_demo:1",
            "material_id": "nm_demo",
            "title": "开篇",
            "summary": "主角陷入困境。",
            "relevance": 3,
        }], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    import_candidate_labels(queries_path, candidates_path)

    payload = yaml.safe_load(queries_path.read_text(encoding="utf-8"))
    assert payload[0]["judgments"] == {"chapter:nm_demo:1": 3}
    assert payload[0]["status"] == "labeled"


def test_evaluate_cases_returns_per_query_type_and_overall_metrics(tmp_path):
    """评分报告不能只保留总体平均值。"""
    queries_path = tmp_path / "queries.yaml"
    _write_queries(queries_path, {"chapter:nm_demo:1": 3})
    cases = load_search_cases(queries_path)

    report = evaluate_cases(
        cases,
        lambda _case, _limit: [_result("chapter:nm_demo:1")],
    )

    assert report["per_query"][0]["case_id"] == "chapter_001"
    assert report["per_query"][0]["precision@10"] == 0.1
    assert report["by_document_type"]["chapter"]["mrr"] == 1.0
    assert report["overall"]["ndcg@10"] == 1.0


def test_golden_query_seed_has_required_distribution():
    """首批真实查询应覆盖计划规定的六类检索需求。"""
    path = Path("eval/search_queries.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert len(payload) == 30
    assert Counter(item["document_type"] for item in payload) == {
        "chapter": 10,
        "event": 10,
        "character": 3,
        "outline": 3,
        "world": 3,
        "detail": 1,
    }
    assert all(item["status"] == "awaiting_human_labels" for item in payload)
    assert all(item["judgments"] == {} for item in payload)
