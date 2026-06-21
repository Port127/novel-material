---
name: nm-search
description: 使用 nm-search 或启动 nm-search 时，用于检索小说素材参考；不适用于未显式点名该 Skill 的普通搜索请求。
---

# nm-search

统一检索入口，根据查询意图路由到七类质量优先检索命令。

## 触发约束

此 skill **仅通过显式调用触发**。

### ⛔ 不触发的场景
- 用户提到搜索、查询但未提及 nm-search
- 日常对话中的"找一下""查一下"
- 用户未显式引用 @nm-search

### ✅ 触发条件
必须同时满足：
1. 用户明确说出"使用 nm-search"或"启动 nm-search"，或显式引用 @nm-search
2. 用户提供了明确的检索意图

## 执行命令

```bash
nm search chapter "开局困境" --limit 10 --mode quality --json
```

## 检索类型与路由

根据查询意图选择对应的检索命令：

| 用户意图 | 命令 | 主要参数 | 返回内容 |
|----------|------|------|----------|
| 章纲/章节功能 | `nm search chapter` | 章节摘要、来源、邻章 |
| 具体事件/情境 | `nm search event` | 事件参考 |
| 全书前提/结构 | `nm search outline` | 大纲结构 |
| 人物塑造 | `nm search character` | 人物档案 |
| 世界观/势力/规则 | `nm search world` | 设定实体 |
| 序列/节拍 | `nm search detail` | 细纲参考 |
| 深度写作洞察 | `nm search insight` | insight YAML |

通用参数：`--mode quality|exact`、`--candidate-limit N`、`--time-budget N`、`--limit N`、`--json`。

## 结果约束

- 检查 `trace.degraded` 与 `degradation_reasons`，说明召回、重排或上下文降级。
- 保留 `result_id`、`material_id`、`source` 和 `neighbors`。
- 结果是参考样例，不是事实答案或最终小说内容；理解、糅合与生成由外部 Agent 完成。
- 人工 Golden Query 基线尚未完成，不得声称混合检索或重排优于 4096 维精确模式。

## 前置条件

- 数据库已初始化（`nm storage init-db`）
- 至少有一本小说已完成流水线（数据已同步到 DB）
- `.env` 中 `DATABASE_URL` 配置正确

## 路由判断指南

当用户的查询比较模糊时，按以下优先级判断：

1. 如果提到"力量体系/势力/地图/规则" → `nm search world`
2. 如果提到"大纲/结构/三幕" → `nm search outline`
3. 如果提到"开局/第N章/写法" → `nm search chapter`
4. 如果提到"人物/角色/导师/反派" → `nm search character`
5. 如果提到具体事件（"告别/打斗/突破"） → `nm search event`
