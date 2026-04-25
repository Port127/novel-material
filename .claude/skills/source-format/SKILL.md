---
name: source-format
description: 清洗入库后的原文 source.txt，生成格式报告和章节索引；优先使用固化脚本 source_format.py
---

# 任务

对已入库原文做格式层清洗，产出：

- `source.txt`
- `format_report.yaml`
- `chapter_index.yaml`

## 边界

用于：
- `material-add` 后的格式清洗
- 大纲生成前的文本整理

不用于：
- 修改剧情内容
- 代替分析阶段

## 输入

- `material_id`

## 默认执行路径

### 1. 前置检查

- `material_id` 存在
- `source.txt` 存在
- 当前状态允许格式化

### 2. 优先跑固化脚本

默认执行：

```bash
python scripts/core/source_format.py \
  data/novels/{material_id}/source.txt \
  data/novels/{material_id}/source.txt \
  data/novels/{material_id}/format_report.yaml \
  --index data/novels/{material_id}/chapter_index.yaml
```

脚本负责：

- 繁简转换
- 广告清理
- 引号修复
- 标点统一
- 章节标准化
- 章节连续性检测

### 3. 检查输出

至少检查：

- `format_report.yaml` 已生成
- `chapter_index.yaml` 已生成
- 是否存在 `suspicious` / 缺章 / 重复章 / 短章

### 4. 必要时动态补充

只有脚本明显不适配当前文本格式时，才额外补脚本或规则。

动态补充应写到 `scripts/generated/`，不要污染核心脚本。

### 5. 更新状态

在 `meta.yaml` 的 `pipeline` 内写入：

- `formatted = true`
- `format_date`
- `chapters`

## 输出要求

至少输出：

- 章节数
- 修复摘要
- 是否有缺章 / 短章 / suspicious 项
- 报告与章节索引位置

## 关键硬约束

- 原地清洗 `source.txt`
- 只做格式处理，不改剧情内容
- 优先使用固化脚本

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/report-fields.md`
- `../../../scripts/core/source_format.py`
- `../../../docs/schemas/format-report.schema.yaml`
- `../../../AGENTS.md`
