---
name: pipeline-events
description: 事件拆分 + 索引构建流水线（novel-events all → build-index）
when_to_use: 素材分析完成（status=tagged），需要拆分全书事件并建索引
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

对已分析的素材执行全书事件拆分和索引构建。

**串联 2 个子 skill：`novel-events`（all 模式） → `build-index`。**

这是整个流程中**最耗时**的阶段（几十到上百批次），专门设计为可跨对话恢复。

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`
2. 确认 `status` 为 `tagged` 或更高
3. 确认 `outline/_index.yaml`、`characters/_index.yaml` 存在（事件拆分需要参考）
4. 检查 `events/` 目录已处理的章节，确定恢复起点

## 恢复逻辑

| 状态 | 行为 |
|------|------|
| 无 events 目录或为空 | 从第 1 章开始 |
| events 部分完成 | 计算已覆盖章节，从未处理章节继续 |
| events 全部完成，无索引 | 跳过 events，直接执行 build-index |
| events + 索引都完成，无 source_entities.json | 执行步骤 5（实体提取） → 步骤 6 → 步骤 7 |
| events + 索引都完成 + source_entities.json，无 completeness_report | 执行步骤 6（交叉验证） → 步骤 7 |
| events + 索引都完成 + completeness_report 且有 critical/warning，无 backfill | 执行步骤 7（AI 补录） → 重新验证 |
| events + 索引都完成 + completeness_report（无 critical/warning 或已补录），refined=false 或缺失 | 进入 pipeline-finalize |
| events + 索引都完成 + refined=true + refine_hash 匹配当前事件 | 输出"已完成" |
| events + 索引都完成 + refined=true + refine_hash 不匹配（事件有变化） | 进入 pipeline-finalize（重新精调） |

> ⚠️ **refine_hash 检测**：当 refined=true 时，必须检查 `meta.yaml` 中的 `refine_hash` 是否与当前事件数据匹配。
> - 如果不匹配，说明事件有变化（如 ai-backfill 新建了事件），需要重新精调。
> - 匹配检测方法：运行 `extract_refine_data.py --no-update-meta`，对比输出的 hash 与 meta.yaml 中的 refine_hash。

检测已覆盖章节的方法：
1. 扫描 `events/` 中所有 `ev*.yaml` 文件
2. 提取章节号，与 `chapter_index.yaml`（或 source.txt 扫描结果）对比
3. 找出缺失章节范围

## 执行步骤

### 1. 预览

```
📋 事件流水线预览

素材：{name} ({material_id})
总章节：{total_chapters}

事件拆分状态：
  已完成：{done_chapters}/{total_chapters} 章（{done_events} 个事件）
  待处理：第 {start}-{end} 章
  预计批次：{batch_count} 批

将执行：
  1. novel-events (all)  → 拆分剩余章节事件
  2. build-index         → 构建倒排索引 + 事件清单

⚠️ 事件拆分将自动循环分批执行
⚠️ 每 30 批建议开新对话恢复，避免上下文膨胀

确认开始？(yes/no)
```

### 2. 执行 novel-events（all 模式）

读取 `novel-events/SKILL.md` 并按其指令执行，关键参数：

- 模式：`all`（自动循环分批）
- 起始章节：从未覆盖的第一章开始
- 质量审计：每批完成后运行 `quality_audit.py --batch {本批范围}`

**⚠️ 关键：`--batch` 参数只传本批范围（如 `421-450`），不传累积范围（如 `1-450`）。**

每批完成后输出进度：

```
[批次 {n}/{total}] 第 {start}-{end} 章完成，{event_count} 个事件 ✅ (diversity={diversity})
```

### 3. 对话分段策略

事件拆分是长耗时任务，context window 会逐步膨胀。**必须**执行以下控制：

- **每处理 30 批**：输出分段提醒
  ```
  ⏸️ 已完成 30 批，建议开新对话恢复：
     /pipeline-events {material_id}
  ```
- **批间不累积上下文**：每批只读当前批的原文，上一批的输出不带入下一批
- **进度持久化**：每批完成后立即更新 `meta.yaml`，即使对话中断也不丢失进度

### 4. 执行 build-index

全书事件完成后，**先写入中间状态标记**，再读取 `build-index/SKILL.md` 并执行：

**4a. 写入中间状态（防中断丢失）**

```yaml
status: complete
pipeline:
  current_stage: build-index
  events_in_progress: false
  index_building: true
  index_built: false
```

> ⚠️ 此标记在 build-index 开始前写入，即使 build-index 过程中断，
> 下次恢复也能知道"events 已完成，只需重建索引"。

**4b. 执行 build-index**

读取 `build-index/SKILL.md` 并执行：

- 构建 `events_index.yaml`（倒排索引）
- 构建 `events_manifest.yaml`（事件清单）
- 构建 SQLite 索引
- 聚合全局人物/剧情索引

**4c. 更新最终状态**

```yaml
status: complete
pipeline:
  current_stage: complete
  stages_completed: [..., events, build-index]
  events_processed: [1-{total_chapters}]
  events_in_progress: false
  index_building: false
  index_built: true
  index_at: {timestamp}
```

**4d. 暂不串联 pipeline-finalize**

> ⚠️ 索引完成后**不要**立即进入 pipeline-finalize。
> 必须先执行步骤 5-7（实体提取 → 交叉验证 → AI 补录），
> 确保事件数据完整后再进入精调。

### 5. 实体提取（extract-source-entities）

索引构建完成后，**从原文提取客观实体清单**，为后续交叉验证做准备：

```bash
python scripts/core/extract_source_entities.py {material_id}
```

输出 `source_entities.json`，包含原文中所有角色/地点/势力/物品/术语
的出场统计（章节号 + 出现次数）。

> ⚠️ 此步骤不依赖 AI 判断，纯粹基于已有名册做正向匹配。

### 6. 交叉验证（validate-completeness）

运行完整性验证脚本，对比原文实体 vs 事件记录：

```bash
python scripts/core/validate_completeness.py {material_id}
```

输出 `completeness_report.yaml`，标记遗漏的 critical/warning 项。

### 7. AI 补录（ai-backfill）

如果 completeness_report 中有 critical 或 warning 项：

读取并执行 `ai-backfill/SKILL.md`，对遗漏实体进行定向补录。
- 每批处理 3-5 个实体
- 只读相关章节，不读全文
- 补录完成后重新验证

如果 completeness_report 中无 critical/warning，跳过此步骤。

### 8. 更新状态

```yaml
status: complete
pipeline:
  current_stage: complete
  stages_completed: [..., events, build-index]
  events_processed: [1-{total_chapters}]
  events_in_progress: false
  index_building: false
  index_built: true
  index_at: {timestamp}
  entities_extracted: true
  entities_extracted_at: {timestamp}
  completeness_validated: true
  completeness_score: {rate}
  completeness_critical_count: {n}
  refine_hash: ""  # 空，等待 refine 时填写
```

如果执行了 AI 补录，追加以下字段：
```yaml
  backfill_done: true
  backfill_at: {timestamp}
  backfill_summary:
    entities_backfilled: {n}
    events_updated: {n}
    events_created: {n}
```

**更新状态后，检查 `meta.yaml` 的 `pipeline.refined` 字段**：
- 如果 `refined=false` 或缺失 → 读取并执行 `pipeline-finalize/SKILL.md`
- 如果 `refined=true` + `refine_hash` 匹配当前事件 → 跳过 finalize，直接输出完成报告
- 如果 `refined=true` + `refine_hash` 不匹配（事件有变化）→ 读取并执行 `pipeline-finalize/SKILL.md`（重新精调）

> ⚠️ hash 匹配检测：运行 `extract_refine_data.py --no-update-meta`，对比输出的 `events_hash` 与 meta.yaml 中的 `refine_hash`。

> ⚠️ 由 novel-pipeline continue 调用时，跳过此串联步骤（调度器负责串联）。
> 由 pipeline-events 独立调用时，必须执行此串联逻辑。

### 9. 输出报告

```
✅ 事件拆分 + 索引构建 + 完整性验证完成

📚 素材：{name}
📖 总章节：{total_chapters}章
🎬 事件总数：{total_events}个
📊 覆盖率：100%

📄 倒排索引：events_index.yaml
📄 事件清单：events_manifest.yaml
📄 SQLite：data/material.db

后续操作：
  /pipeline-finalize {material_id}    # 精调 + 统计报告
  /novel-pipeline full {material_id}  # 继续完整流程
```

## 硬约束

- MUST 先预览再执行
- MUST `--batch` 参数只传本批新增范围，不传累积范围
- MUST 每批完成后立即写入文件 + 更新 meta.yaml
- MUST 每 30 批输出分段提醒
- MUST 批间不累积上下文（不把上一批事件数据带入下一批）
- MUST events 全部完成后才执行 build-index
- MUST build-index 开始前写入 index_building=true 中间状态
- MUST build-index 完成后立即运行 extract_source_entities.py + validate_completeness.py
- MUST completeness_report 中有遗漏时执行 ai-backfill
- MUST 实体提取、交叉验证、补录全部完成后，再检查 refined 状态并决定是否进入 pipeline-finalize
- NEVER 在一个对话内强行跑完超长小说的全部事件（适时提醒分段）
- NEVER 由 novel-pipeline 调度器调用时重复串联 pipeline-finalize

## References

- [novel-events/SKILL.md](../novel-events/SKILL.md)
- [build-index/SKILL.md](../build-index/SKILL.md)
- [ai-backfill/SKILL.md](../ai-backfill/SKILL.md)
- [AGENTS.md](../../../AGENTS.md)