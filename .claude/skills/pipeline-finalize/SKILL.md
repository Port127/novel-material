---
name: pipeline-finalize
description: 精调 + 统计报告流水线（refine → novel-stats）
when_to_use: 事件拆分和索引都完成后（status=complete），生成精调产出和统计报告
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

在事件数据齐备后，精调早期产出物并生成全书统计报告。

**串联 2 个子 skill：`refine` → `novel-stats`。**

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`
2. **阻断状态检测（优先）**：
   - 如果 `status = backfill-blocked`
     → **拒绝执行**：输出明确阻断信息并退出
     ```
     🚫 ========================================
     🚫 拒绝执行 pipeline-finalize
     🚫 ========================================
     🚫   当前状态: backfill-blocked
     🚫   原因: 数据完整性不足
     🚫
     🚫   必须: 先执行 /ai-backfill {material_id}
     🚫   禁止: 绕过阻断直接进入精调
     🚫 ========================================
     ```
3. 认 `status` 为 `complete` 或更高
4. 确认 `events_index.yaml` 或 `events_manifest.yaml` 存在
5. 确认 `outline/_index.yaml`、`characters/_index.yaml`、`tags.yaml` 存在
6. **完备性报告检查**：
   - 读取 `completeness_report.yaml`（如存在）
   - 如果 `completeness_score < 0.5` 且 `backfill_done=false`
     → **拒绝执行**：输出「事件数据不完整，请先完成 ai-backfill」
     → 并更新 `status: backfill-blocked`
7. **章节覆盖率检查**：
   - 扫描所有事件的 `chapters` 字段
   - 如果主线连续未覆盖章节 > 3
     → **警告**：输出「主线覆盖不完整，精调结果可能不准确」

## 恢复逻辑

| 状态 | 行为 |
|------|------|
| refined=false, stats_generated=false, refine_batches 缺失或 current_batch=1 | 从 refine batch-1 开始 |
| refined=false, current_batch=2 | 从 refine batch-2（钩子验证）继续 |
| refined=false, current_batch=2b | 从 refine batch-2b（线索交汇验证）继续 |
| refined=false, current_batch=3 | 从 refine batch-3（人物弧线）继续 |
| refined=false, current_batch=4 | 从 refine batch-4（关系验证）继续 |
| refined=false, current_batch=5 | 从 refine batch-5（世界观精调）继续 |
| refined=false, current_batch=6 | 从 refine batch-6（清理汇总）继续 |
| refined=true, stats_generated=false | 跳过 refine，执行 novel-stats |
| 均已完成 | 输出"已完成" |

## 执行步骤

### 1. 预览

```
📋 精调+统计流程预览

素材：{name} ({material_id})
状态：{status}
事件数：{total_events}

将执行：
  1. refine       → 精调大纲/世界观/人物/标签（基于事件数据反哺）
  2. novel-stats  → 生成统计报告 + 交互图表 + 关系图谱

{如有跳过} ⏭️ 已完成阶段将跳过：{列表}

确认开始？(yes/no)
```

### 2. 执行 refine（分批精调）

读取 `refine/SKILL.md` 并按其分批执行策略执行。

refine 分为 6 个批次（batch-1 到 batch-6），每批完成后立即写入并更新状态：

| 批次 | 操作 | 数据源 | 上下文控制 |
|------|------|--------|-----------|
| batch-1 | 统计数据合并 | `refine_input.json` | 只读 JSON，不读原始事件 |
| batch-2 | 钩子验证 | 钩子清单 + 涉及的少数事件 | 每次验证 10 个钩子 |
| batch-2b | 线索交汇验证 | `cross_thread_events.yaml` + 涉及事件 | 每次验证 10 个交汇点 |
| batch-3 | 人物弧线 | 人物出场统计 + profiles/ | 每次处理 5-10 个角色 |
| batch-4 | 关系验证 | relations.yaml + 涉及事件 | 每次验证 5 对关系 |
| batch-5 | 世界观精调 | 地点/势力统计 + lore/ | 只读统计 + 个别事件 |
| batch-6 | 清理汇总 | 汇总前 6 批结果 | 不读原始事件 |

**关键：每批完成后立即写入文件 + 更新 meta.yaml，如果中断下次可从断点恢复。**

主要产出：
- 钩子网络建立（统一处理钩子铆合链）
- 线索交汇验证（校准主线与支线/感情线的关联纽带）
- 节奏曲线补充
- 人物弧线细化
- 关系演变时间线
- 世界观信息补充
- 小说级标签校准

### 3. 执行 novel-stats

读取 `novel-stats/SKILL.md` 并执行。主要产出：

- `stats.yaml`（原始统计数据）— **必须生成**
- `stats.md`（Mermaid 可视化报告）— **必须生成**
- `stats.html`（ECharts 交互报告 + 关系图谱）— **必须生成**

**输出文件完整性检查**：
生成完成后，验证三个文件是否都存在。如缺少任一文件，补生成后才可标记完成。

### 4. 更新状态

```yaml
status: refined
pipeline:
  stages_completed: [..., refine, novel-stats]
  refined: true
  refined_at: {timestamp}
  stats_generated: true
  stats_at: {timestamp}
```

### 5. 输出最终报告

```
✅ 精调 + 统计报告完成

📚 素材：{name}

精调结果：
  📖 outline/ — 钩子网络 +{n}条，节奏曲线 +{n} 点，线索交汇 +{n} 个
  👥 characters/ — {n} 角色弧线细化，{n} 关系演变
  🗺️ worldbuilding/ — {n} 处补充
  🏷️ tags.yaml — {n} 维度校准

统计报告：
  📊 stats.yaml / stats.md / stats.html
  🎬 事件总数：{total_events}
  📈 转折点：{turning_count}
  🪝 钩子网络：{total}/{verified}/{pending}（验证率 {rate}%）
  🔗 线索交织：{intersections}个交汇点（密度 {density}）

📁 全部完成！素材状态：refined

后续操作：
  /material-search [关键词]             # 关键词检索
  /material-search-event [需求描述]     # 多维标签检索
  /material-search-context [写作上下文] # 写作事件检索
```

## 硬约束

- MUST 先预览再执行
- MUST refine 只读事件数据，不读原文
- MUST novel-stats 只读事件数据 + manifest/index，不读原文
- MUST 精调前备份待修改文件（.bak）
- MUST 支持从中断点恢复
- NEVER 编造统计数据（无信号写 TBD）

## References

- [refine/SKILL.md](../refine/SKILL.md)
- [novel-stats/SKILL.md](../novel-stats/SKILL.md)
- [AGENTS.md](../../../AGENTS.md)
