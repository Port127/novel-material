#!/usr/bin/env python3
"""检索容量实验的安全入口与近似候选质量门禁。

当前入口只生成隔离实验计划；真实百万级数据构造必须显式传入
``--confirm-large``，并由后续数据库执行器在 ``search_benchmark`` schema 内完成。
"""

import argparse
import json
import platform
from pathlib import Path

LARGE_ROWS = 2_500_000
MIN_CANDIDATE_RECALL = 0.98
MAX_NDCG_DROP = 0.01
MAX_P95_SECONDS = 180.0


def candidate_gate(
    *,
    candidate_recall: float,
    exact_ndcg: float,
    candidate_ndcg: float,
    p95_seconds: float = 0.0,
    lost_qualified_queries: int = 0,
) -> bool:
    """判断近似候选实验是否满足进入生产设计讨论的硬门禁。"""
    return (
        candidate_recall >= MIN_CANDIDATE_RECALL
        and exact_ndcg - candidate_ndcg <= MAX_NDCG_DROP
        and p95_seconds <= MAX_P95_SECONDS
        and lost_qualified_queries == 0
    )


def requires_large_confirmation(rows: int) -> bool:
    """250 万行及以上必须显式确认。"""
    return rows >= LARGE_ROWS


def estimate_storage_gib(rows: int, dimensions: int = 4096) -> float:
    """粗估原始 float32 向量及行开销，不作为配额承诺。"""
    bytes_per_row = dimensions * 4 * 1.35
    return rows * bytes_per_row / 1024**3


def build_experiment_plan(args: argparse.Namespace) -> dict:
    """生成不会修改数据库的可审计实验计划。"""
    return {
        "schema": "search_benchmark",
        "rows": args.rows,
        "queries": str(args.queries),
        "mode": args.mode,
        "candidate_experiment": args.candidate_experiment,
        "candidate_limit": max(1000, args.candidate_limit),
        "estimated_storage_gib": round(estimate_storage_gib(args.rows), 2),
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "required_metrics": [
            "p50_seconds",
            "p95_seconds",
            "peak_memory_mb",
            "database_buffers",
            "throughput_qps",
            "per_query_results",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成隔离的检索容量实验计划")
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--mode", choices=("exact", "quality"), default="exact")
    parser.add_argument("--candidate-experiment", action="store_true")
    parser.add_argument("--candidate-limit", type=int, default=1000)
    parser.add_argument("--confirm-large", action="store_true")
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows 必须大于 0")
    if not args.queries.exists():
        parser.error(f"查询文件不存在：{args.queries}")
    if requires_large_confirmation(args.rows) and not args.confirm_large:
        parser.error("250 万行实验必须显式传入 --confirm-large")
    return args


def main() -> None:
    args = parse_args()
    print(json.dumps(build_experiment_plan(args), ensure_ascii=False, indent=2))
    print("仅生成实验计划，未连接数据库、未创建数据。")


if __name__ == "__main__":
    main()
