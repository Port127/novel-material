"""Golden Query 加载、候选导出、人工标签合并与评分。"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from novel_material.eval.search_metrics import evaluate_ranking, recall_at_k
from novel_material.search.models import SearchResult

SearchCallable = Callable[["SearchEvalCase", int], list[SearchResult]]


@dataclass(frozen=True)
class SearchEvalCase:
    """一条可人工标注、可重复评分的检索查询。"""

    id: str
    query: str
    document_type: str
    filters: dict[str, Any]
    judgments: dict[str, int]
    require_diversity: bool
    require_neighbors: bool


def load_search_cases(path: Path) -> list[SearchEvalCase]:
    """从 YAML 加载评测查询并校验基础结构。"""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("检索评测文件必须是查询列表")

    cases: list[SearchEvalCase] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条查询必须是对象")
        case_id = item.get("id") or f"第 {index} 条查询"
        for field in ("id", "query", "document_type"):
            if not item.get(field):
                raise ValueError(f"{case_id} 缺少必填字段 {field}")

        filters = item.get("filters", {})
        judgments = item.get("judgments", {})
        if not isinstance(filters, dict):
            raise ValueError(f"{case_id} 的 filters 必须是对象")
        if not isinstance(judgments, dict):
            raise ValueError(f"{case_id} 的 judgments 必须是对象")

        cases.append(SearchEvalCase(
            id=str(item["id"]),
            query=str(item["query"]),
            document_type=str(item["document_type"]),
            filters=filters,
            judgments={str(key): value for key, value in judgments.items()},
            require_diversity=bool(item.get("require_diversity", False)),
            require_neighbors=bool(item.get("require_neighbors", False)),
        ))
    return cases


def validate_labeled_cases(cases: list[SearchEvalCase]) -> None:
    """拒绝空标注以及 0～3 之外的相关性分数。"""
    for case in cases:
        if not case.judgments:
            raise ValueError(f"{case.id} 缺少人工 judgments")
        for result_id, relevance in case.judgments.items():
            if isinstance(relevance, bool) or relevance not in (0, 1, 2, 3):
                raise ValueError(
                    f"{case.id} 的 {result_id} 相关性必须是 0、1、2、3"
                )


def export_candidates(
    cases: list[SearchEvalCase],
    search_callable: SearchCallable,
    output_path: Path,
    limit: int = 30,
    *,
    minimum_candidates: int = 10,
    relaxed_search_callable: SearchCallable | None = None,
    inventory_search_callable: SearchCallable | None = None,
) -> None:
    """执行检索并导出不带猜测分数的人工标注候选。"""
    if not 1 <= minimum_candidates <= limit:
        raise ValueError("minimum_candidates 必须介于 1 和 limit 之间")

    rows: list[dict[str, Any]] = []
    for case in cases:
        pool: list[tuple[SearchResult, str]] = []
        seen: set[str] = set()

        for result in search_callable(case, limit)[:limit]:
            if result.result_id in seen:
                continue
            seen.add(result.result_id)
            pool.append((result, "strict"))

        target = min(limit, minimum_candidates)
        if len(pool) < target and relaxed_search_callable is not None:
            for result in relaxed_search_callable(case, limit):
                if result.result_id in seen:
                    continue
                seen.add(result.result_id)
                pool.append((result, "relaxed"))
                if len(pool) >= target:
                    break

        if len(pool) < target and inventory_search_callable is not None:
            for result in inventory_search_callable(case, limit):
                if result.result_id in seen:
                    continue
                seen.add(result.result_id)
                pool.append((result, "inventory"))
                if len(pool) >= target:
                    break

        if not pool:
            rows.append({
                "case_id": case.id,
                "query": case.query,
                "result_id": None,
                "material_id": None,
                "title": "",
                "summary": "",
                "relevance": None,
                "status": "no_candidates",
                "candidate_source": "none",
            })
            continue
        rows.extend({
            "case_id": case.id,
            "query": case.query,
            "result_id": result.result_id,
            "material_id": result.material_id,
            "title": result.title,
            "summary": result.summary,
            "relevance": None,
            "candidate_source": candidate_source,
        } for result, candidate_source in pool)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(rows, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def import_candidate_labels(queries_path: Path, candidates_path: Path) -> None:
    """将人工填写的候选分数合并回查询 YAML。"""
    queries = yaml.safe_load(queries_path.read_text(encoding="utf-8"))
    candidates = yaml.safe_load(candidates_path.read_text(encoding="utf-8"))
    if not isinstance(queries, list) or not isinstance(candidates, list):
        raise ValueError("查询文件和候选文件都必须是列表")

    by_case: dict[str, dict[str, int]] = defaultdict(dict)
    for row in candidates:
        if not isinstance(row, dict):
            raise ValueError("候选标注行必须是对象")
        case_id = row.get("case_id")
        result_id = row.get("result_id")
        relevance = row.get("relevance")
        if not case_id or not result_id:
            raise ValueError("候选标注缺少 case_id 或 result_id")
        if isinstance(relevance, bool) or relevance not in (0, 1, 2, 3):
            raise ValueError(f"{case_id} 的 {result_id} 尚未完成 0～3 分标注")
        by_case[str(case_id)][str(result_id)] = relevance

    known_case_ids = {str(item.get("id")) for item in queries if isinstance(item, dict)}
    unknown_case_ids = set(by_case) - known_case_ids
    if unknown_case_ids:
        raise ValueError(f"候选包含未知 case: {sorted(unknown_case_ids)}")

    for item in queries:
        case_id = str(item.get("id"))
        if not by_case.get(case_id):
            raise ValueError(f"{case_id} 没有可导入的人工标注")
        item["judgments"] = by_case[case_id]
        item["status"] = "labeled"

    queries_path.write_text(
        yaml.safe_dump(queries, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    validate_labeled_cases(load_search_cases(queries_path))


def _average_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    metric_names = (
        "recall@50",
        "recall@100",
        "mrr",
        "precision@10",
        "ndcg@10",
        "distinct_materials@10",
        "elapsed_ms",
    )
    if not rows:
        return {name: 0.0 for name in metric_names}
    return {
        name: sum(float(row[name]) for row in rows) / len(rows)
        for name in metric_names
    }


def evaluate_cases(
    cases: list[SearchEvalCase],
    search_callable: SearchCallable,
) -> dict[str, Any]:
    """返回逐查询、按文档类型和总体宏平均指标。"""
    validate_labeled_cases(cases)
    per_query: list[dict[str, Any]] = []

    for case in cases:
        started = perf_counter()
        results = search_callable(case, 100)[:100]
        elapsed_ms = (perf_counter() - started) * 1000
        ranked = [result.result_id for result in results]
        material_ids = {result.result_id: result.material_id for result in results}
        top_ten = evaluate_ranking(ranked, case.judgments, material_ids, k=10)
        per_query.append({
            "case_id": case.id,
            "query": case.query,
            "document_type": case.document_type,
            "recall@50": recall_at_k(ranked, case.judgments, 50),
            "recall@100": recall_at_k(ranked, case.judgments, 100),
            **top_ten,
            "elapsed_ms": elapsed_ms,
            "result_ids": ranked,
        })

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_query:
        grouped[row["document_type"]].append(row)

    return {
        "per_query": per_query,
        "by_document_type": {
            document_type: _average_metrics(rows)
            for document_type, rows in sorted(grouped.items())
        },
        "overall": _average_metrics(per_query),
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    """将完整评测报告写成可审计 JSON。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
