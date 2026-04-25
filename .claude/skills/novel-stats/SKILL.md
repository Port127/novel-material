---
name: novel-stats
description: 基于事件与索引数据生成统计报告；统一输出 stats.yaml、stats.md、stats.html 三件套
---

# 任务

从事件数据生成统一统计结果，并输出：

- `stats.yaml`
- `stats.md`
- `stats.html`

**只读事件与索引数据，不读原文。**

## 前置检查

开始前必须确认：

1. `events/` 已完成
2. 优先使用 `events_manifest.yaml`
3. `outline/`、`characters/`、`worldbuilding/` 可供补充统计

## 单一数据源原则

三件套中，**`stats.yaml` 是唯一权威数据源**。

执行顺序固定为：

1. 先统计并写 `stats.yaml`
2. 再用 `stats.yaml` 渲染 `stats.md`
3. 再用 `stats.yaml` 渲染 `stats.html`

禁止让 `stats.md` 或 `stats.html` 自己重新统计。

## 默认执行路径

### 1. 汇总统计输入

优先读取：

- `events_manifest.yaml`
- `events_index.yaml`
- `outline/hooks_network.yaml`
- `events/cross_thread_events.yaml`
- `characters/_index.yaml`
- `characters/relations.yaml`

必要时再少量读取 event YAML。

### 2. 生成 `stats.yaml`

至少应包含：

- 基础数量统计
- 标签分布
- 转折节奏
- 紧张度曲线
- 节奏模式
- 钩子统计
- 线索交织统计
- 人物统计
- 情感统计
- 关系图谱原始数据

### 3. 渲染 `stats.md`

使用 `stats.yaml` 作为输入，输出轻量可读版本：

- 表格
- Mermaid 图表
- 关键观察结论

### 4. 渲染 `stats.html`

同样使用 `stats.yaml`，输出交互版 HTML：

- 图表库可用 ECharts
- 结构可复用已有 `stats.html` 骨架
- 只替换数据部分，不另起一套口径

### 5. 完整性检查

只有三个文件都存在且非空，才允许写：

```yaml
pipeline:
  stats_generated: true
```

缺任一文件都不能标记完成。

## 核心硬约束

- 不读原文
- 不编造统计数据；无信号写 `TBD`
- `stats.md` / `stats.html` 必须来自 `stats.yaml`
- 三件套缺一不可
- 输出中的示例数值必须来自当前素材，不要保留模板数字

## 输出要求

报告至少包含：

- 三个文件是否都已生成
- 核心指标摘要
- 使用了哪些输入源
- 若有缺失，缺的是哪一类数据

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/metrics.md`
- `references/rendering.md`
- `../../../docs/schemas/event-unit.schema.yaml`
- `../../../AGENTS.md`
