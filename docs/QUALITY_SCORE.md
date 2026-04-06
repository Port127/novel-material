# Novel Material 质量评分卡

## 评分维度

|| 维度 | 权重 | 当前得分 | 目标 | 备注 |
|------|------|----------|------|------|
| 文档覆盖 | 20% | 70% | 80% | 14 docs 中 10 个已完成 |
| Skill 可用性 | 30% | 100% | 90% | 14 个 skills 全部定义 |
| 检索准确性 | 25% | TBD | 85% | 待实际 skill 执行验证 |
| 素材库完整性 | 15% | 100% | 95% | 2 个小说素材已入库 |
| 标签规范度 | 10% | 100% | 90% | tags.yaml 完整定义 6 层 |

## 总分

**当前：TBD**（部分维度需实际 skill 执行验证）

**目标：85+**

## Eval Suite 状态

|| 项目 | 状态 | 信号来源 |
|------|------|----------|
| Tasks 定义 | ✅ 完成 | `evals/tasks/material-skills-regression.yaml` (19 tasks) |
| Graders 定义 | ✅ 完成 | deterministic + rubric + Unknown 逃逸口 |
| Runner 实现 | ✅ 完成 | `evals/run.py` |
| Baseline 快照 | ✅ 完成 | `docs/evals/results/baselines/20260405T161900Z--material-skills-regression.json` |
| 正负案例平衡 | ✅ 完成 | 10:9 比例 |
| 人工校准 | ❌ 待执行 | rubric 需 5+ 样本校准 |

### Baseline 结果（模拟）

```
Run ID: 20260405T161900Z--material-skills-regression
Total Tasks: 19
pass@1: 100% (simulated)
pass@3: 100% (simulated)
Balance: 10 positive / 9 negative
Saturation: ALERT (需要更难 capability 任务)
```

**注：** 当前 baseline 为模拟执行结果，需实际 skill 执行后更新。

## 改进计划

|| 优先级 | 改进项 | 状态 | 计划 |
|--------|--------|------|------|
| P0 | 建立 Eval Suite | ✅ 完成 | 已完成 |
| P0 | 人工校准 rubric | 🔴 | M3 |
| P1 | 实际 skill 执行验证 | 🔴 | 待执行 |
| P1 | 验证索引一致性 | 🔴 | M3 |
| P2 | 补充设计文档 | 🟡 | 进行中 |
| P3 | 补充更多素材 | 🟡 | 持续 |

## Checklist

### 文档

- [x] AGENTS.md（≤100行）— 78 行
- [x] ARCHITECTURE.md
- [x] docs/DESIGN.md
- [x] docs/PLANS.md
- [x] docs/QUALITY_SCORE.md
- [x] docs/product-specs/index.md
- [ ] docs/design-docs/core-beliefs.md（需更新）
- [x] docs/exec-plans/tech-debt-tracker.md
- [x] docs/evals/index.md
- [x] docs/evals/graders/deterministic.md
- [x] docs/evals/graders/rubrics.md（含 Unknown 逃逸口 + 校准流程）
- [x] docs/evals/results/baselines/README.md

### Skills（活跃）

- [x] material-add
- [x] source-format
- [x] novel-outline
- [x] novel-characters
- [x] novel-tags
- [x] novel-scenes
- [x] build-index
- [x] refine
- [x] novel-stats
- [x] novel-pipeline
- [x] material-search
- [x] material-search-scene
- [x] tag-add
- [x] tag-merge

### Eval Suite

- [x] evals/tasks/ 定义 — 19 tasks (10 positive + 9 negative)
- [x] evals/graders/ 定义 — deterministic + rubric
- [x] evals/run.py Runner 实现
- [x] baseline 运行 — 模拟结果已生成
- [ ] 评分自动化 — 需实际 skill 执行
- [ ] 人工校准 — rubric 需 5+ 样本校准

## Saturation 警告

当前模拟 baseline 显示 100% pass rate，建议：
- 添加更难的 capability 任务
- 执行实际 skill 验证获取真实数据

## Last Updated

2026-04-06