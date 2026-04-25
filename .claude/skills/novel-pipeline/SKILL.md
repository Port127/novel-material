---
name: novel-pipeline
description: 路由完整处理、快速处理、断点恢复和单阶段执行；用于 full、quick、continue、stage 模式的总调度
---

# 任务

作为总调度器，负责：

1. 识别模式和参数
2. 做阶段前置检查和阻断判断
3. 路由到子流水线
4. 汇总执行结果

**不要在这里展开原子 skill 细节。** 具体执行、校验、状态写回由子流水线负责。

## 适用边界

用于：
- 一键跑完整流程
- 只跑前两阶段骨架分析
- 从中断点恢复
- 指定跑某个子流水线

不用于：
- 直接替代 `pipeline-ingest` / `pipeline-analyze` / `pipeline-events` / `pipeline-finalize`
- 直接替代原子 skill

## 输入

| 模式 | 形式 | 行为 |
|------|------|------|
| `full` | `/novel-pipeline full [路径]` | ingest → analyze → events → finalize |
| `quick` | `/novel-pipeline quick [路径]` | ingest → analyze |
| `continue` | `/novel-pipeline continue [material_id]` | 从当前真实进度恢复 |
| `stage` | `/novel-pipeline stage [material_id] [阶段]` | 只跑指定子流水线 |

如果参数缺失，只补问最小必要信息；参数齐全时直接执行，不做额外确认停顿。

## 总体路由

```text
novel-pipeline
  ├── pipeline-ingest
  ├── pipeline-analyze
  ├── pipeline-events
  └── pipeline-finalize
```

## 默认执行路径

### 1. 识别模式

- 有文件路径且表达完整处理意图 → `full`
- 有文件路径且表达快速骨架意图 → `quick`
- 有 `material_id` 且表达恢复/继续意图 → `continue`
- 有 `material_id` 且指定阶段名 → `stage`

### 2. 前置阻断

进入任一子流水线前必须检查：

| 条件 | 行为 |
|------|------|
| `status = backfill-blocked` | 立即拒绝执行，提示先跑 `ai-backfill`，不要继续任何子流水线 |
| 准备进入 finalize，且 `completeness_report.yaml` 显示未通过或 `critical_count > 0` | 拒绝进入 finalize；若已写成 `backfill-blocked`，提示先跑 `ai-backfill` |

### 3. 路由执行

#### `full`

按顺序执行：

1. `pipeline-ingest`
2. `pipeline-analyze`
3. `pipeline-events`
4. `pipeline-finalize`

任一阶段失败或被门控阻断时，立即停止，并报告：
- 停在什么阶段
- 哪个校验失败
- 下一步应该执行什么

#### `quick`

按顺序执行：

1. `pipeline-ingest`
2. `pipeline-analyze`

完成后停止，不进入事件拆分。

#### `stage`

仅路由到指定阶段：

| 阶段别名 | 路由 |
|----------|------|
| ingest / 入库 | `pipeline-ingest` |
| analyze / 分析 | `pipeline-analyze` |
| events / 事件 | `pipeline-events` |
| finalize / 精调 / 统计 | `pipeline-finalize` |

#### `continue`

优先看**文件系统真实状态**，再参考 `meta.yaml`。不要只信状态字段。

恢复判断优先级：

1. `events/`、`events_index.yaml`、`source_entities.json`、`completeness_report.yaml`
2. `pipeline.refine_batches`、`refine_hash`、`stats.yaml` / `stats.md` / `stats.html`
3. `meta.yaml` 的 `status` 与 `pipeline.*`

常见路由：

| 真实状态 | 路由 |
|----------|------|
| 只有原文，未格式化 | `pipeline-ingest` |
| 已格式化，未完成分析 | `pipeline-analyze` |
| 已 `tagged`，但 events 不完整 / 索引缺失 / 完备性未验证 | `pipeline-events` |
| 已 `complete`，但 refine 或 stats 未完成 | `pipeline-finalize` |
| refine 与 stats 都完成 | 输出“全部完成” |

## 子流水线职责边界

| 子流水线 | 负责内容 |
|----------|----------|
| `pipeline-ingest` | 入库、格式清洗、章节索引、meta 基础状态 |
| `pipeline-analyze` | outline / worldbuilding / characters / tags |
| `pipeline-events` | 事件拆分、索引、完整性验证、必要时补录 |
| `pipeline-finalize` | refine、stats、最终状态收口 |

调度器只负责串联，不重复写它们的内部规则。

## 输出要求

完成后统一输出：

- 执行了哪些子流水线
- 哪些阶段跳过了，原因是什么
- 当前停在什么状态
- 下一步推荐命令

如果中断恢复，还要明确：
- 依据哪些文件判断恢复点
- 是否检测到状态字段滞后

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/recovery.md`：continue 的详细恢复矩阵
- `../pipeline-ingest/SKILL.md`
- `../pipeline-analyze/SKILL.md`
- `../pipeline-events/SKILL.md`
- `../pipeline-finalize/SKILL.md`
- `../../../AGENTS.md`
