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

## 质量门控（所有模式通用）

每个子流水线完成后必须执行对应的质量检查，检查不通过时**停止流水线并报告**，不进入下一阶段。

| 阶段完成 | 检查项 | 工具 | 通过标准 |
|----------|--------|------|---------|
| pipeline-ingest | YAML schema 校验 | `validate_yaml.py meta {id}` | 0 error |
| pipeline-ingest | 章节连续性 | 检查 format_report.yaml | 无缺失章节或用户确认 |
| pipeline-analyze | YAML schema 校验 | `validate_yaml.py outline {id}` 等（逐个执行） | 0 error |
| pipeline-analyze | 人物名册完整性 | 检查 characters/_index.yaml | protagonist/antagonists 不为空 |
| pipeline-events | YAML schema 抽检 | `validate_yaml.py event {id}` + 随机 3 个事件 | 0 error |
| pipeline-events | 章节覆盖检查 | 扫描 events/*.yaml 的 chapters 字段 | 主线连续未覆盖 ≤ 3 章 |
| pipeline-events | 完备性验证 | `validate_completeness.py {id}` | completeness_score ≥ 0.5 或 backfill_done=true |
| pipeline-finalize | YAML schema 校验 | `validate_yaml.py outline {id}` + `validate_yaml.py characters {id}` | 0 error |

## 阶段前置检查（防止绕过硬约束）

每个子流水线开始前，必须执行前置检查并输出检查清单：

### 检查模板

```
📋 进入 {阶段名} 前置检查

必须确认：
  [ ] 已读取完整 {阶段}/SKILL.md（≥ 前 200 行）
  [ ] 已理解阻断规则（如有）
  [ ] 已理解硬约束列表（MUST/NEVER）

当前状态：
  status: {status}
  completeness_score: {score}
  backfill_done: {backfill}

{如有阻断} 🚫 检测到阻断状态，禁止继续
{如有警告} ⚠️ 检测到警告状态，建议修复

确认开始？(yes/no)
```

### 阻断状态检测（所有阶段通用）

进入任何子流水线前，首先检查：

| 条件 | 行为 |
|------|------|
| `status = backfill-blocked` | **拒绝执行**，输出明确阻断信息并退出 |
| `completeness_score < 0.5` 且 `backfill_done=false` 且尝试进入 finalize | **拒绝执行**，输出阻断信息 |

**阻断时的输出**：
```
🚫 ========================================
🚫 拒绝执行 {阶段名}
🚫 ========================================
🚫   当前状态: {status}
🚫   原因: 数据完整性不足
🚫
🚫   必须: 先执行 /ai-backfill {material_id}
🚫   禁止: 绕过阻断直接进入下一阶段
🚫 ========================================
```

## 术语表

| 术语 | 定义 | 出现位置 |
|------|------|---------|
| **事件批（event batch）** | 每次处理的一组连续章节（通常 3-5 章），产出若干事件 | pipeline-events, novel-events |
| **精调批（refine batch）** | 每次处理的一组精调任务（10 个钩子/5-10 个角色/5 对关系） | refine, pipeline-finalize |
| **补录批（backfill batch）** | 每次处理的一组遗漏实体（3-5 个实体） | ai-backfill, pipeline-events |

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

读取 `meta.yaml` 中的 `pipeline` 字段，**结合文件系统实际状态**，判断当前进度：

**Step 1: 读取 meta.yaml 状态**

| 条件 | 路由到 | 说明 |
|------|--------|------|
| status=raw，formatted 缺失或 false | pipeline-ingest（补格式化） | 原文未清洗 |
| status=raw，formatted=true | pipeline-analyze | 清洗完成，开始分析 |
| status=outlined | pipeline-analyze（从缺失步骤恢复） | 分析进行中 |
| status=tagged | 进入 Step 2 文件系统检查 | 可能是事件拆分中或已完成但未更新状态 |
| status=complete，refined 缺失或 false，source_entities.json 存在 | pipeline-finalize | 索引已建+数据已验证，开始精调 |
| status=complete，refined 缺失或 false，source_entities.json 缺失 | 进入 Step 2 文件系统检查 | 数据尚未验证，需检查实体提取状态 |
| status=complete，refined=true，refine_batches.cleanup_done=false | pipeline-finalize（从断点恢复 refine） | 精调被中断，继续 refine |
| status=complete，refined=true，stats_generated 缺失 | pipeline-finalize（跳 refine） | 精调完成，补统计 |
| status=refined | 输出"全部完成" | 所有阶段均已完成 |

**Step 2: 文件系统兜底检查（当 status=tagged 或 status=complete+source_entities 缺失 时执行）**

当 meta.yaml 的 status 仍为 `tagged`，或 status 为 `complete` 但
`source_entities.json` 缺失时，检查实际文件存在性，防止状态更新滞后：

| 文件检查结果 | 路由到 | 说明 |
|-------------|--------|------|
| events/ 目录不存在或为空 | pipeline-events | 事件尚未开始拆分 |
| events/ 部分完成 | pipeline-events（从断点恢复） | 事件拆分被中断 |
| events/ 全部覆盖 + events_index.yaml 存在 + source_entities.json 缺失 | pipeline-events（继续执行实体提取） | 事件完成但实体未提取 |
| events/ 全部覆盖 + events_index.yaml 存在 + source_entities.json 存在 + completeness_report.yaml 缺失 | pipeline-events（继续执行交叉验证） | 实体已提取但尚未验证 |
| events/ 全部覆盖 + events_index.yaml 存在 + source_entities.json 存在 + completeness_report.yaml 存在 + 有 critical/warning + backfill_done=false | pipeline-events（执行 AI 补录） | 有遗漏需要补录 |
| events/ 全部覆盖 + events_index.yaml 存在 + source_entities.json 存在 + completeness_report.yaml 存在 + 无 critical/warning 或 backfill_done=true + refined=false/缺失 | pipeline-finalize | 事件+索引+验证+补录已完成，进精调 |
| events/ 全部覆盖 + 无 events_index.yaml 或 index_building=true | pipeline-events（跳过 events，直接 build-index） | 事件完成，索引未建完 |

> ⚠️ 文件系统检查优先于 meta.yaml 状态。
> 如果文件实际已完成但 status 未更新，以文件为准，避免重复跑 events。

**Step 1b: 完备性阻断检查**

如果 `completeness_validated=true` 且 `completeness_score < 0.5` 且 `backfill_done=false`：
→ **阻止进入 finalize**，输出阻断信息，建议执行 `/pipeline-events {id}` 进行补录

预览恢复计划后等待确认。

### 3. 执行子流水线

用户确认后，**依次调用**子流水线的 SKILL.md：

#### full 模式执行序列

1. 读取并执行 `pipeline-ingest/SKILL.md`
   - 产出：material_id, source.txt, format_report.yaml
   - 失败 → 停止，报告

   **质量检查**：
   ```bash
   python scripts/core/validate_yaml.py format {material_id}
   ```
   - 校验失败 → 停止并报告具体错误，不进入 pipeline-analyze
   - 检查 `format_report.yaml` 章节连续性，有缺失章节需用户确认

2. 读取并执行 `pipeline-analyze/SKILL.md`
   - 产出：outline/、worldbuilding/、characters/ 文件夹结构, tags.yaml
   - 失败 → 停止，报告

   **质量检查**：
   ```bash
   python scripts/core/validate_yaml.py outline {material_id}
   python scripts/core/validate_yaml.py worldbuilding {material_id}
   python scripts/core/validate_yaml.py characters {material_id}
   python scripts/core/validate_yaml.py novel-tags {material_id}
   ```
   - 任一校验失败 → 停止并报告
   - 检查 `characters/_index.yaml` 的 `roster` 中 `protagonists` 和 `antagonists` 不为空
   - 检查 `outline/_index.yaml` 的 `structure_summary.acts` ≥ 2
   - 检查不通过 → 停止，不进入 pipeline-events

3. 读取并执行 `pipeline-events/SKILL.md`
   - 产出：events/*.yaml, events_index.yaml, events_manifest.yaml
   - 附加：source_entities.json（原文实体提取）, completeness_report.yaml（完整性验证）
   - **此阶段可能跨对话**——pipeline-events 会在适当时机提醒开新对话
   - 如果在此阶段中断，下次 `continue` 会路由到 pipeline-events 恢复

   **质量检查**：
   ```bash
   python scripts/core/validate_yaml.py event {material_id}
   ```
   - 随机抽检 3 个事件文件，校验失败 → 停止并报告
   - 扫描所有事件的 `chapters` 字段，主线连续未覆盖 > 3 章 → 强制补切事件
   - 运行 `validate_completeness.py {material_id}`：
     - `completeness_score < 0.5` 且 `backfill_done=false` → **强制阻断**，执行 ai-backfill，禁止进入 pipeline-finalize
     - 补录完成后重新验证，达标后才放行

4. 读取并执行 `pipeline-finalize/SKILL.md`
   - 前置检查：如果 `completeness_score < 0.5` 且 `backfill_done=false` → 拒绝执行
   - refine 分批执行（6 个批次，每批完成后写入）
   - 产出：精调后的 outline/characters/tags/worldbuilding + stats.*
   - 失败 → 停止，报告

   **质量检查**：
   ```bash
   python scripts/core/validate_yaml.py outline {material_id}
   python scripts/core/validate_yaml.py characters {material_id}
   ```
   - 精调后 YAML 校验失败 → 停止并报告

每个子流水线内部已有自己的预览/确认逻辑，**由调度器调用时跳过子流水线的预览**（调度器层面已经确认过了），直接进入执行。

#### continue 模式执行

只调用需要恢复的子流水线及其后续子流水线。例如：
- 从 pipeline-ingest 恢复 → 执行 ingest → analyze → events → finalize
- 从 pipeline-analyze 恢复 → 执行 analyze → events → finalize
- 从 pipeline-events 恢复 → 执行 events → finalize
  - 注意：pipeline-events 完成后会自动检查并进入 pipeline-finalize
- 从 pipeline-finalize 恢复（refine 未开始）→ 执行 refine → novel-stats
- 从 pipeline-finalize 恢复（refine 中，current_batch=N）→ 从 batch-N 继续 refine → novel-stats
- 从 pipeline-finalize 恢复（refine 完成，stats 缺失）→ 仅执行 novel-stats

### 4. 最终报告

所有子流水线完成后输出：

```
✅ 完整处理流程结束

📚 素材 ID：{material_id}
📁 文件夹：data/novels/{material_id}/

生成文件：
  - meta.yaml              (元数据)
  - source.txt             (清洗后原文)
  - format_report.yaml     (格式清洗报告)
  - outline/              (故事大纲文件夹，已精调)
  - worldbuilding/        (世界观文件夹，已精调)
  - characters/           (人物文件夹，已精调)
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
  index_building: false
  index_built: false
  entities_extracted: false
  completeness_validated: false
  backfill_done: false
  refine_hash: ""
  refined: false
  refine_batches:
    current_batch: 1
    batches_completed: 0
    stats_merged: false
    hooks_verified: false
    characters_refined: false
    relations_verified: false
    worldbuilding_refined: false
    cleanup_done: false
  stats_generated: false
```

## 硬约束

- MUST 先输出预览，仅在用户确认后开始执行
- MUST 调用子流水线的 SKILL.md，不直接调用原子 skill
- MUST continue 模式通过 meta.yaml + 文件系统兜底判断恢复点
- MUST status=tagged 时执行文件系统兜底检查（events/ 覆盖情况 + 索引存在性）
- MUST 每个子流水线完成后立即持久化状态
- NEVER 在用户确认后再次停下等待确认（子流水线内部也不再确认）
- NEVER 试图在一个对话内强行完成超长小说的全部流程
- NEVER 手动修改 meta.yaml 的状态字段（如 refined、completeness_score、backfill_done）
  → 状态字段必须由脚本写入，手动修改视为绕过质量门控

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