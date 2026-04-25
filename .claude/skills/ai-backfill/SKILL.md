---
name: ai-backfill
description: 根据 completeness_report 定向补录遗漏实体；按小批次回读相关章节，更新已有事件或新建事件
---

# 任务

根据完整性报告中的遗漏项，定向补录事件数据。

## 边界

用于：
- `completeness_report.yaml` 中存在 `critical` / `warning`
- 需要补人物、地点、势力、物品或术语遗漏

不用于：
- 全书重跑事件拆分
- 大范围重读原文

## 输入

- `material_id`

## 默认执行路径

### 1. 前置检查

- `completeness_report.yaml` 存在
- `issues` 非空
- `source_entities.json` 可用

### 2. 小批次处理

每批只处理少量遗漏实体，默认 3-5 个。

对每个实体：

1. 根据 `source_entities.json` 定位相关章节
2. 只读相关章节，不读全文
3. 判断是：
   - 追加到已有事件
   - 新建事件
   - 仅背景提及，可标记跳过

### 3. 每批都要落盘

每批完成后必须：

- 更新事件文件
- 写 `backfill_progress.yaml`
- 记录本批处理结果

### 4. 补录完成后复验

全部处理完后，必须重新跑：

```bash
python scripts/core/validate_completeness.py {material_id}
```

### 5. 状态写回

只有复验通过后，才写：

- `pipeline.backfill_done = true`
- `pipeline.backfill_at`

## 输出要求

至少输出：

- 处理了多少实体
- 追加了多少事件
- 新建了多少事件
- 跳过了多少背景提及
- 覆盖率前后变化

## 关键硬约束

- 每次只读相关章节
- 批次要小
- 每批都更新进度
- 补录后必须重新验证
- 不能跳过 critical 项

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/decision-rules.md`
- `../../../docs/schemas/event-unit.schema.yaml`
- `../novel-events/SKILL.md`
- `../build-index/SKILL.md`
- `../../../AGENTS.md`
