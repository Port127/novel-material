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

分析用户输入，路由到最合适的检索方式：

| 输入特征 | 路由 | 示例 |
|----------|------|------|
| 书名/作者名 | 素材级匹配 | "三体""刘慈欣" |
| 角色名 | 人物索引 + 事件索引 | "叶文洁""吕树" |
| 事件需求描述 | 直接路由到 `/material-search-event` | "恋人吵架""弱者反杀" |
| 写作上下文描述 | 直接路由到 `/material-search-context` | "我在写一个师徒告别的章节" |
| 类型/标签词 | 小说级标签匹配 | "修真""都市重生" |
| 风格/基调词 | 小说级标签匹配（`prose_style`/`tone`/`writing_strength`） | "冷叙述风格""热血基调""对话写得好的" |
| 混合 | 先素材级缩小范围，再事件级精确匹配 | "三体中的对决事件" |

### 2. 素材级匹配

读取 `data/index.yaml`，匹配 `name`, `author`。
如命中，返回素材基本信息和状态。

#### 2a. 风格/基调过滤

如果用户输入包含风格相关词汇，读取各小说的 `tags.yaml`（小说级标签），按以下字段过滤：
- `style.prose` → 匹配 `prose_style` 值（如"冷叙述""华丽"）
- `tone` → 匹配基调值（如"热血""沉重"）
- `style.strength` → 匹配写作长板（如"对话""氛围营造"）
- `tropes` → 匹配套路（如"废柴逆袭""重生复仇"）

返回匹配的小说列表，并标注匹配的风格维度。如果后续还有事件级检索需求，在这些小说范围内进行。

### 3. 事件级关键词匹配（脚本优先）

遵循**三级回退**策略：

**Level 1 — SQLite 查询**（优先，如存在 `data/material.db`）：

```bash
# 角色名 → 按人物检索
python scripts/core/search.py event --character {角色名} --limit 10

# 关键词 → 全文搜索 summary/title
python scripts/core/search.py text --query {关键词} --limit 10

# 可映射到标签值 → 多维检索
python scripts/core/search.py event --event-type {映射值} --limit 10
```

**Level 2 — YAML 倒排索引**（SQLite 不可用时）：
- 如关键词是角色名 → 查 `events_index.yaml` 的 `character` 维度
- 如关键词可映射到标签值 → 查对应维度
- 命中后只读取候选 event YAML 获取详情

**Level 3 — 遍历事件文件**（兜底）：
- 仅在无索引且无清单时使用
- 分批遍历 `data/novels/*/events/*.yaml`，匹配 `title`, `summary`, `characters`

### 4. 返回结果

按相关度排序返回，优先展示完全匹配，其次部分匹配。

## 输出格式

```
🔍 搜索结果：{query}

---

## 结果 1
📚 来源：{name}（{id}）
🎬 事件：{title}
> {summary}

---

📁 共找到 {count} 个相关结果

💡 更精确的检索：/material-search-event {需求描述}
```

## 注意事项

- 如果明显是事件需求，直接路由到 `/material-search-event`，不做关键词匹配
- 返回原文定位信息（`text_range`），方便用户追溯
- 事件级检索必须遵循索引优先原则，避免无谓遍历全部事件文件
- 跨小说检索时，对每部小说独立走三级回退，合并结果后排序

## References

- [AGENTS.md](../../../AGENTS.md)
- [ARCHITECTURE.md](../../../ARCHITECTURE.md) — 架构、检索策略、跨项目集成
