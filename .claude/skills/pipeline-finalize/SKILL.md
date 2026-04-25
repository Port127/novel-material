---
name: pipeline-finalize
description: 在事件、索引与完整性验证通过后执行 refine 和 novel-stats，完成最终收口
---

# 任务

执行收尾阶段：

1. `refine`
2. `novel-stats`

## 边界

用于：
- `pipeline-events` 完成后进入最终精调与统计
- 从 refine / stats 中断点恢复

不用于：
- 绕过完整性阻断直接 finalize

## 输入

- `material_id`

## 默认执行路径

### 1. 前置阻断

必须先检查：

- `status != backfill-blocked`
- `completeness_report.yaml` 允许进入 finalize
- `events_index.yaml` 或 `events_manifest.yaml` 已存在
- `outline/`、`characters/`、`tags.yaml` 已存在

### 2. 恢复判断

| 状态 | 动作 |
|------|------|
| refine 未完成 | 先跑或恢复 `refine` |
| refine 已完成、stats 未完成 | 跳过 refine，执行 `novel-stats` |
| 两者都完成 | 输出“已完成” |

### 3. 执行 refine

调用 `../refine/SKILL.md`，按其批次恢复逻辑继续，不在这里重复展开批次细节。

### 4. 执行 novel-stats

调用 `../novel-stats/SKILL.md`，确保三件套都生成：

- `stats.yaml`
- `stats.md`
- `stats.html`

### 5. 更新最终状态

只有 refine 与 stats 都完成时，才写：

- `status = refined`
- `pipeline.refined = true`
- `pipeline.stats_generated = true`

## 输出要求

至少输出：

- 是从哪一步恢复的
- refine 是否完成
- stats 三件套是否齐全
- 当前最终状态

## 关键硬约束

- 被 `backfill-blocked` 时必须拒绝
- 不读原文
- 不在本 skill 内重复写 refine/stats 细节

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `../refine/SKILL.md`
- `../novel-stats/SKILL.md`
- `../../../AGENTS.md`
