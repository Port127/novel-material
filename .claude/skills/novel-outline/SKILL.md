---
name: novel-outline
description: 读取原文并生成文件夹结构的大纲骨架，包括结构、节奏、钩子网络与可选情节线模块
---

# 任务

生成全书大纲骨架，输出到 `outline/` 文件夹。

## 边界

用于：
- 首次建立全书结构骨架
- 为后续世界观、人物、事件拆分提供导航

不用于：
- 替代事件拆分
- 精确验证所有钩子回收

## 输入

- `material_id`

## 默认执行路径

### 1. 前置检查

- `source.txt` 存在
- 有 `chapter_index.yaml` 时优先复用

### 2. 阅读策略

根据篇幅选择：

- 短篇：可一次性读取
- 长篇：分段阅读 + 增量汇总

只把结构性摘要传给下一段，不传整段原文。

### 3. 段内提取

每段关注：

- 结构骨架
- 核心事件
- 转折点
- 主要钩子
- 节奏感知
- 情节线索

### 4. 汇总生成模块

至少生成：

- `_index.yaml`
- `structure.yaml`

按需要启用：

- `plotlines.yaml`
- `hooks_network.yaml`
- `pacing_curve.yaml`
- `subplots.yaml`
- `themes.yaml`
- `emotional_arc.yaml`

### 5. 多线叙事初步交汇

如识别多线叙事，只做**初步交汇锚点**，不要把它当作已验证事实。

### 6. 状态写回

完成后将状态推进到 `outlined`。

## 输出要求

至少输出：

- 幕数 / 序列数
- 启用了哪些模块
- 识别了多少主要钩子
- 输出目录

## 关键硬约束

- 长篇不一次性读全文
- `structure.yaml` 必须存在
- 钩子网络在本阶段只做初步版

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/module-selection.md`
- `../../../docs/schemas/outline.schema.yaml`
- `../../../AGENTS.md`
