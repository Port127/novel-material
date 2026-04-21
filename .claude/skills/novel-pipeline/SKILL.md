---
name: novel-pipeline
description: 一键流程调度器，编排 4 个子流水线，支持 full/quick/continue/stage 模式
when_to_use: 用户想要一键执行完整流程、从中断点恢复、或批量触发多个 skill
argument-hint: "[模式] [参数]"
arguments: mode, params
---

# 任务

轻量调度器——根据模式参数路由到对应的**子流水线**。

**不直接执行文件操作，不直接调用原子 skill，通过调用子流水线完成。**

## 架构

```
novel-pipeline（调度器）
  ├── pipeline-ingest     → material-add + source-format
  ├── pipeline-analyze    → outline + worldbuilding + characters + tags
  ├── pipeline-events     → novel-events (all) + build-index
  └── pipeline-finalize   → refine + novel-stats
```

每个子流水线是独立的 skill，可单独调用，也可由此调度器串联。

## 流程路由

| 模式 | 触发词 | 执行流水线 | 参数 |
|------|--------|-----------|------|
| `full` | 一键处理、完整流程、全自动 | ingest → analyze → events → finalize | `[路径]` |
| `quick` | 快速处理、仅骨架 | ingest → analyze | `[路径]` |
| `continue` | 继续、恢复、接着处理 | 从中断子流水线恢复 | `[material_id]` |
| `stage` | 指定阶段名 | 仅执行指定子流水线 | `[material_id] [阶段名]` |

## 执行步骤

### 1. 识别意图

根据用户输入判断模式：
- 含文件路径 + 含"一键/完整/全自动" → `full`
- 含文件路径 + 含"快速/骨架" → `quick`
- 含 material_id + 含"继续/恢复" → `continue`
- 含 material_id + 含阶段名（入库/分析/事件/精调） → `stage`

### 2. 生成预览

#### full 模式

```
📋 完整流程预览

素材：{路径}

将分 4 个阶段执行：
  ① pipeline-ingest    → 入库 + 格式清洗
  ② pipeline-analyze   → 大纲 + 世界观 + 人物 + 标签
  ③ pipeline-events    → 全书事件拆分 + 索引构建
  ④ pipeline-finalize  → 精调 + 统计报告

⚠️ 阶段 ①②④ 在当前对话内完成
⚠️ 阶段 ③（事件拆分）耗时最长，大书可能需要多次对话
   每 30 批会提醒开新对话，用 /novel-pipeline continue {id} 恢复

确认开始？(yes/no)
```

#### continue 模式

读取 `meta.yaml` 中的 `pipeline` 字段，判断当前进度：

| 条件 | 路由到 | 说明 |
|------|--------|------|
| status=raw，formatted 缺失或 false | pipeline-ingest（补格式化） | 原文未清洗 |
| status=raw，formatted=true | pipeline-analyze | 清洗完成，开始分析 |
| status=outlined | pipeline-analyze（从缺失步骤恢复） | 分析进行中 |
| status=tagged | pipeline-events | 小说标签已完成，开始事件拆分 |
| status=tagged + events/ 已有部分文件 | pipeline-events（从断点恢复） | 事件拆分被中断 |
| status=complete，refined 缺失或 false | pipeline-finalize | 索引已建，开始精调 |
| status=complete，refined=true，stats_generated 缺失 | pipeline-finalize（跳 refine） | 精调完成，补统计 |
| status=refined | 输出"全部完成" | 所有阶段均已完成 |

预览恢复计划后等待确认。

### 3. 执行子流水线

用户确认后，**依次调用**子流水线的 SKILL.md：

#### full 模式执行序列

1. 读取并执行 `pipeline-ingest/SKILL.md`
   - 产出：material_id, source.txt, format_report.yaml
   - 失败 → 停止，报告

2. 读取并执行 `pipeline-analyze/SKILL.md`
   - 产出：outline.yaml, worldbuilding.yaml, characters.yaml, tags.yaml
   - 失败 → 停止，报告

3. 读取并执行 `pipeline-events/SKILL.md`
   - 产出：events/*.yaml, events_index.yaml, events_manifest.yaml
   - **此阶段可能跨对话**——pipeline-events 会在适当时机提醒开新对话
   - 如果在此阶段中断，下次 `continue` 会路由到 pipeline-events 恢复

4. 读取并执行 `pipeline-finalize/SKILL.md`
   - 产出：精调后的 outline/characters/tags/worldbuilding + stats.*
   - 失败 → 停止，报告

每个子流水线内部已有自己的预览/确认逻辑，**由调度器调用时跳过子流水线的预览**（调度器层面已经确认过了），直接进入执行。

#### continue 模式执行

只调用需要恢复的子流水线及其后续子流水线。例如：
- 从 pipeline-events 恢复 → 执行 events → finalize
- 从 pipeline-finalize 恢复 → 仅执行 finalize

### 4. 最终报告

所有子流水线完成后输出：

```
✅ 完整处理流程结束

📚 素材 ID：{material_id}
📁 文件夹：data/novels/{material_id}/

生成文件：
  - meta.yaml              (元数据)
  - source.txt             (清洗后原文)
  - source.raw.txt         (原始备份)
  - format_report.yaml     (格式清洗报告)
  - outline.yaml           (故事大纲，已精调)
  - worldbuilding.yaml     (世界观设定，已精调)
  - characters.yaml        (人物体系，已精调)
  - tags.yaml              (小说标签，已精调)
  - events/*.yaml          ({N} 个事件)
  - events_index.yaml      (倒排索引)
  - events_manifest.yaml   (事件清单)
  - stats.yaml             (统计数据)
  - stats.md               (可视化报告)
  - stats.html             (交互报告+关系图谱)

状态：refined

后续操作：
  /material-search [关键词]             # 关键词检索
  /material-search-event [需求描述]     # 多维标签检索
  /material-search-context [写作上下文] # 写作事件上下文检索
```

## 状态追踪

状态保存在 `meta.yaml` 的 `pipeline` 字段：

```yaml
pipeline:
  mode: full
  current_stage: events
  stages_completed: [material-add, source-format, outline, worldbuilding, characters, tags]
  events_processed: [1-5, 6-10]
  formatted: true
  index_built: false
  refined: false
  stats_generated: false
```

## 硬约束

- MUST 先输出预览，仅在用户确认后开始执行
- MUST 调用子流水线的 SKILL.md，不直接调用原子 skill
- MUST continue 模式通过 meta.yaml 判断恢复点
- MUST 每个子流水线完成后立即持久化状态
- NEVER 在用户确认后再次停下等待确认（子流水线内部也不再确认）
- NEVER 试图在一个对话内强行完成超长小说的全部流程

## 示例

### 一键完整处理

```
用户: /novel-pipeline full /path/to/novel.txt

novel-pipeline:
  📋 完整流程预览
  ...
  确认开始？

用户: yes

novel-pipeline:
  ━━━ ① pipeline-ingest ━━━
  [1/2] material-add ✅ ID: nm_novel_20260405_x1y2
  [2/2] source-format ✅ 修复 87 处引号，1070 章

  ━━━ ② pipeline-analyze ━━━
  [1/4] novel-outline ✅ 5幕结构
  [2/4] novel-worldbuilding ✅ 3力量等级
  [3/4] novel-characters ✅ 85人
  [4/4] novel-tags ✅ 都市/重生

  ━━━ ③ pipeline-events ━━━
  [批次 1/214] 第 1-5 章 ✅ 15 事件 (diversity=0.87)
  [批次 2/214] 第 6-10 章 ✅ 12 事件
  ...
  ⏸️ 已完成 30 批，建议开新对话：
     /novel-pipeline continue nm_novel_20260405_x1y2
```

### 中断恢复

```
用户: /novel-pipeline continue nm_novel_20260405_x1y2

novel-pipeline:
  📋 恢复预览

  素材：《某某小说》
  当前进度：events 阶段，已处理 150/1070 章

  将恢复执行：
    ③ pipeline-events → 从第 151 章继续
    ④ pipeline-finalize → 精调 + 统计

  确认继续？

用户: yes

novel-pipeline:
  ━━━ ③ pipeline-events（恢复） ━━━
  [批次 31/214] 第 151-155 章 ✅ ...
```

## References

- [pipeline-ingest/SKILL.md](../pipeline-ingest/SKILL.md)
- [pipeline-analyze/SKILL.md](../pipeline-analyze/SKILL.md)
- [pipeline-events/SKILL.md](../pipeline-events/SKILL.md)
- [pipeline-finalize/SKILL.md](../pipeline-finalize/SKILL.md)
- [AGENTS.md](../../../AGENTS.md)
- [ARCHITECTURE.md](../../../ARCHITECTURE.md)