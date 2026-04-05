---
name: material-search
description: 搜索素材库（关键词 + 自动路由）
when_to_use: 用户想要找参考素材
argument-hint: "[关键词或需求描述]"
arguments: query
---

# 任务

在素材库中搜索相关内容，自动路由到最合适的检索方式。

## 输入参数

- `$0+` (query): 搜索关键词或自然语言需求描述

## 执行步骤

### 1. 判断检索类型

分析用户输入：

- **关键词搜索**（如"三体""叶文洁""修真"）→ 走关键词匹配
- **场景需求**（如"恋人吵架""弱者反杀"）→ 路由到 `/material-search-scene`
- **混合**：先走关键词缩小范围，再用标签精确匹配

### 2. 关键词匹配

读取 `data/index.yaml`，匹配 `name`, `author`。
遍历 `data/novels/*/scenes/*.yaml`，匹配 `title`, `summary`, `characters`。

### 3. 返回结果

按相关度排序返回。

## 输出格式

```
🔍 搜索结果：{query}

---

## 结果 1
📚 来源：{name}（{id}）
🎬 场景：{title}
> {summary}

---

📁 共找到 {count} 个相关结果

💡 更精确的检索：/material-search-scene {需求描述}
```

## 注意事项

- 如果明显是场景需求，直接调用 `/material-search-scene`
- 返回原文定位信息，方便用户追溯
