# Baseline Results

Eval baseline 结果存储目录。

## 目录结构

```
baselines/
├── README.md                  # 本文件
├── YYYYMMDDTHHMMSSZ--xxx.json # 各次运行结果
└── latest--xxx.json           # 最新结果副本
```

## 结果格式

```json
{
  "run_id": "20260405T120000Z--material-search",
  "timestamp": "2026-04-05T12:00:00Z",
  "tasks": [
    {
      "task_id": "search-keyword-001",
      "input": { "keyword": "修真" },
      "expected": { "min_results": 1, "contains": "nm_novel_xxx" },
      "result": "pass",
      "grader": "deterministic"
    }
  ],
  "metrics": {
    "pass_rate": 0.85,
    "pass@3": 0.90,
    "avg_score": 4.2
  }
}
```

## 当前状态

**无 baseline 结果** — 待 Eval Suite 建立。

## 相关文档

- [../../index.md](../../index.md)
- [../../../QUALITY_SCORE.md](../../../QUALITY_SCORE.md)