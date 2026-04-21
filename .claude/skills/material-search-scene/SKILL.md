---
name: material-search-scene
description: 按多维标签条件检索事件素材
when_to_use: 用户描述写作需求，需要找参考事件
argument-hint: "[自然语言需求描述]"
arguments: query
---

# 任务

将用户的自然语言需求解析为标签组合，在所有事件中检索匹配的素材。

## 前置检查

1. 读取 `data/tags.yaml` 获取合法标签维度
2. 读取 `data/index.yaml` 获取所有素材列表

## 执行步骤

### 1. 解析需求为标签组合

将用户的自然语言描述拆解为标签条件。

示例：
- "恋爱中吵架" → `relationship: 恋人` + `event_type: 争吵`
- "弱者反杀强者" → `power_dynamic: 翻转` + `event_type: 对决`
- "雨中告别" → `time_weather: 雨` + `event_type: 告别`
- "催泪但不煽情" → `reader_effect: 催泪` + `technique: 留白`
- "不知道怎么写对话" → 看上下文推断 `dialogue_type` + `relationship`

向用户确认解析结果，或直接搜索。

### 2. 检索事件

**优先调用 search.py 查 SQLite**（如存在 `data/material.db`）：

```bash
python scripts/core/search.py event --event-type 对决 --emotion 燃 --relationship 师徒 --limit 10
```

脚本自动完成 AND 交集、匹配度排序、结果精简，输出 YAML 格式结果。LLM 只需读脚本输出，不必加载索引文件。

支持的过滤参数（对应 tags.yaml 的所有维度）：
- `--event-type`, `--conflict`, `--stakes`, `--emotion`, `--reader-effect`
- `--relationship`, `--interaction`, `--character-moment`, `--power-dynamic`
- `--plot-stage`, `--plot-function`, `--pacing`
- `--technique`, `--dialogue-type`, `--pov`, `--info-delivery`
- `--setting`, `--scale`, `--time-weather`
- `--character`（人物名）, `--material`（限定小说）
- `--tension-min`, `--tension-max`

AND 匹配无结果时，脚本自动放宽为 OR 并按匹配度排序。

**次选使用 YAML 倒排索引**（SQLite 不可用时）：
1. 对每个标签条件，从 `events_index.yaml` 中查找匹配的 event_id 列表
2. 对多个条件取交集（AND 逻辑）
3. 只读取命中的 event YAML 获取详情

**兜底遍历**（无索引时）：
遍历 `data/novels/*/events/*.yaml`，对每个事件：
- 匹配标签条件（AND 逻辑）
- 计算匹配度（匹配的维度越多越靠前）

### 3. 排序与返回

按匹配度降序排列，返回 Top-N 结果。

## 输出格式

```
🔍 检索条件：{解析后的标签组合}

---

## 匹配 1 ⭐⭐⭐⭐⭐
📚 来源：{novel_name}（{material_id}）
🎬 事件：{event_title}（{event_id}）
📖 章节：{chapter}

> {summary}

🏷️ 匹配标签：{matched_tags}
📍 原文位置：source.txt 行 {start}-{end}

---

## 匹配 2 ⭐⭐⭐⭐
...

---

📊 共找到 {count} 个匹配事件
```

## 注意事项

- 自然语言解析要宽容，用户不会用精确标签名搜索
- 如果匹配结果为空，放宽条件（去掉最弱的一个维度）重试
- 返回 summary 和原文定位，让用户可以去看原文
- 如果用户描述涉及剧情结构，也参考 `plot_index.yaml`
