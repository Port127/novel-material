---
name: ai-backfill
description: 根据 completeness_report 对遗漏实体进行 AI 定向补录（分批执行）
when_to_use: 交叉验证后发现原文实体在事件记录中遗漏（completeness_report.yaml 中有 critical/warning 项）
argument-hint: "[material_id] [--batch N]"
arguments: material_id
---

# 任务

根据 `completeness_report.yaml` 中的遗漏项，定向回读原文相关章节，
补充到已有事件或新建事件，修复数据完整性。

**核心原则：只读遗漏实体相关的章节，不读全文，控制上下文量。**

## 前置检查

1. 读取 `data/novels/{material_id}/completeness_report.yaml`
2. 确认 `issues` 字段中有 critical 或 warning 项
3. 读取 `data/novels/{material_id}/meta.yaml`，确认状态

## 恢复逻辑

| 状态 | 行为 |
|------|------|
| 无 completeness_report | 先运行 validate_completeness.py |
| report 中无 critical/warning | 输出"无需补录" |
| 有未处理项 | 从第 1 个 critical 项开始 |
| backfill_progress.yaml 存在 | 从上次中断的项继续 |

## 执行步骤

### 1. 预览

```
📋 AI 补录预览

素材：{name} ({material_id})
遗漏项统计：
  critical：{n} 项
  warning：{n} 项

补录范围：
  角色：{n} 个（如：叶文洁、汪淼）
  地点：{n} 个
  势力：{n} 个
  物品：{n} 个
  术语：{n} 个
  章节：{n} 个范围

将分批处理，每批 3-5 个实体。
确认开始？(yes/no)
```

### 2. 分批补录

**每批处理 3-5 个遗漏实体**，执行以下流程：

#### 2a. 定位原文

对每个遗漏实体：
- 从 `source_entities.json` 读取其 `chapters` 列表
- 读取 `source.txt` 中对应章节的原文
- 每次只读少量章节（≤ 5 章），控制上下文量

#### 2b. 判断补录方式

对每个实体，读取原文后判断：

| 判断结果 | 操作 |
|----------|------|
| 实体在已有事件的章节范围内 | 追加到对应事件的 `characters`/`setting`/相关字段 |
| 实体涉及的事件尚未创建 | 创建新事件 YAML，遵循 event-unit.schema.yaml |
| 实体只是背景描写中提及，无需独立记录 | 跳过，标记为 resolved=background |

#### 2c. 更新事件文件

- 追加到已有事件：直接修改对应 `events/ev*.yaml`
- 新建事件：创建 `events/ev_{thread}_{seq}.yaml`
- 每补录一个实体，在 `backfill_progress.yaml` 中记录

#### 2d. 批次完成

每批完成后：
- 输出进度
- 更新 `backfill_progress.yaml`
- 如果还有未处理的项，提示继续下一批

```
[批次 {n}] 已补录 {m} 个实体
  - {entity1}: 追加到 ev_main_003
  - {entity2}: 新建 ev_main_045
  - {entity3}: 跳过（背景提及）

剩余 {remaining} 个待处理。
继续？(yes/no)
```

### 3. 补录完成后验证

全部实体补录完成后：

1. **重新运行交叉验证**：
   ```bash
   python scripts/core/validate_completeness.py {material_id}
   ```

2. **检查覆盖率是否提升**：
   - 如果仍有 critical/warning → 继续补录
   - 如果覆盖率达标 → 进入下一步

3. **更新状态**：
   ```yaml
   pipeline:
     backfill_done: true
     backfill_at: {timestamp}
     backfill_summary:
       entities_backfilled: {n}
       events_updated: {n}
       events_created: {n}
   ```

### 4. 输出报告

```
✅ AI 补录完成

素材：{name}
补录统计：
  处理实体总数：{n}
  追加到已有事件：{n}
  新建事件：{n}
  跳过（背景提及）：{n}

覆盖率变化：
  补录前：{before}%
  补录后：{after}%

后续操作：
  /pipeline-finalize {material_id}    # 进入精调阶段
```

## 硬约束

- MUST 每次只读与当前遗漏实体相关的章节（≤ 5 章），绝不读全文
- MUST 每批处理 3-5 个实体，控制上下文量
- MUST 每批完成后更新 backfill_progress.yaml
- MUST 补录完成后重新运行 validate_completeness.py 验证
- MUST 新建事件时严格遵循 event-unit.schema.yaml
- NEVER 因为补录而修改已精调完成的事件（除非确认为同一事件）
- NEVER 跳过 critical 级别的遗漏项

## References

- [event-unit.schema.yaml](../../../docs/schemas/event-unit.schema.yaml)
- [novel-events/SKILL.md](../novel-events/SKILL.md)
- [build-index/SKILL.md](../build-index/SKILL.md)
- [AGENTS.md](../../../AGENTS.md)
