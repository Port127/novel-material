---
name: pipeline-ingest
description: 入库+格式清洗流水线（material-add → source-format）
when_to_use: 用户有新文件要入库，或触发 full pipeline 的第一阶段
argument-hint: "[文件路径]"
arguments: path
---

# 任务

将一个新素材文件入库并完成格式清洗，产出可供后续分析的干净 `source.txt`。

**串联 2 个子 skill：`material-add` → `source-format`。**

## 前置检查

1. 确认文件路径存在
2. 读取 `data/index.yaml` 检查是否已入库（去重）

## 执行步骤

### 1. 预览

```
📋 入库流程预览

素材：{文件路径}

将执行：
  1. material-add   → 入库（创建文件夹 + meta.yaml）
  2. source-format  → 格式清洗（繁简/广告/引号/章节名/缺章检测）

确认开始？(yes/no)
```

等待用户确认后执行。

### 2. 执行 material-add

读取 `material-add/SKILL.md` 并按其指令执行。收集产出的 `material_id`。

### 3. 执行 source-format

读取 `source-format/SKILL.md` 并按其指令执行，传入 `material_id`。

### 4. 更新 pipeline 状态

在 `meta.yaml` 中记录：

```yaml
pipeline:
  mode: ingest
  stages_completed: [material-add, source-format]
  formatted: true
  format_date: {today}
  chapters: {total_chapters}
```

### 5. 输出报告

```
✅ 入库+清洗完成

📚 ID：{material_id}
📄 名称：{name}
📁 文件夹：data/novels/{material_id}/
📊 清洗结果：{章节数}章，修复{N}处
📑 章节索引：chapter_index.yaml 已生成

后续操作：
  /pipeline-analyze {material_id}    # 生成大纲/世界观/人物/标签
  /novel-pipeline continue {material_id}  # 继续完整流程
```

## 硬约束

- MUST 先预览再执行
- MUST 按顺序串联（material-add 成功后才执行 source-format）
- MUST 记录 pipeline 状态到 meta.yaml
- NEVER 跳过 source-format（即使原文看起来很干净）

## References

- [material-add/SKILL.md](../material-add/SKILL.md)
- [source-format/SKILL.md](../source-format/SKILL.md)
- [AGENTS.md](../../../AGENTS.md)
