---
name: material-search-context
description: 面向写作场景的上下文检索，为 chapter-draft / plot-suggest 等创作 skill 提供参考素材
when_to_use: 正在写某一章/某个情节，需要从素材库中找类似场景、人物原型、技法参考
argument-hint: "[写作上下文描述]"
arguments: context
---

# 任务

根据写作上下文（当前章节概要、角色状态、情节需求），从素材库中检索**最相关的参考素材**，返回可直接用于创作参考的结构化结果。

与 `material-search-scene` 的区别：
- `material-search-scene`: 用户主动检索，按标签精确匹配
- `material-search-context`: 面向创作流程，自动从写作上下文推断检索维度，**同时检索场景、人物、技法**三个维度

## 输入

用户传入的写作上下文可能包含：
- 当前章节概要或大纲片段
- 角色当前状态和困境
- 想要达到的效果（催泪/爽感/悬念等）
- 想要参考的技法或风格
- 创作中遇到的具体问题（"不知道怎么写告别""需要一个翻转的灵感"）

## 执行步骤

### 1. 解析写作上下文

从上下文中提取多个检索维度：

| 上下文信号 | 映射到的检索维度 |
|------------|-----------------|
| 角色名/类型 | `character_index.yaml` 人物检索 |
| 场景描述 | `scene_type` + `setting` + `scale` |
| 情感需求 | `emotion` + `reader_effect` |
| 人物关系 | `relationship` + `interaction` + `power_dynamic` |
| 冲突类型 | `conflict` + `stakes` |
| 结构位置 | `plot_stage` + `plot_function` + `pacing` |
| 技法需求 | `technique` + `dialogue_type` + `info_delivery` |
| 风格参考 | `prose_style` + `tone`（小说级标签） |
| 人物心理 | `character_moment` + `psychology.*` 字段 |

### 2. 多维度并行检索

**优先使用 `scripts/core/search.py` 查 SQLite**（如存在 `data/material.db`），同时在三个维度执行检索：

#### 2a. 场景参考

```bash
python scripts/core/search.py scene --scene-type {推断} --emotion {推断} --relationship {推断} --limit 10
```

脚本自动完成 AND 交集和匹配度排序。AND 无结果时自动放宽为 OR。

如需更精细控制，可多次调用脚本用不同维度组合：
- 先用核心维度（scene_type + emotion）广搜
- 再加限定维度（relationship + technique）精筛

#### 2b. 人物参考

```bash
python scripts/core/search.py character --archetype {推断} --role protagonist --limit 10
```

支持按原型、角色类型、道德光谱检索。心理深度字段（`fatal_flaw` 等）在结果中自动返回。

SQLite 不可用时，退回读取 `data/character_index.yaml`。

#### 2c. 技法参考

```bash
python scripts/core/search.py scene --technique {推断} --reader-effect {推断} --limit 5
```

从场景中检索使用了特定技法的案例，结合 `reader_effect` 反推合适技法。

### 3. 组装结果

将三个维度的结果交叉排序，按**与写作上下文的相关度**排列。

## 输出格式

```
🎯 写作上下文分析：
  场景类型：{推断}
  情感基调：{推断}
  关键维度：{推断的标签组合}

---

## 📖 场景参考

### 参考 1 ⭐⭐⭐⭐⭐
📚 来源：{novel_name}
🎬 场景：{title}（{scene_id}）
📖 章节：{chapter}
> {summary}
🏷️ 匹配：{matched_tags}
💡 参考价值：{为什么这个场景对当前写作有用}

### 参考 2 ⭐⭐⭐⭐
...

---

## 👥 人物参考

### {角色名}（{novel_name}）
  原型：{archetype} | 功能：{narrative_function}
  弧线：{arc_summary}
  致命缺陷：{fatal_flaw}
  执念：{obsession}
  💡 参考价值：{为什么这个角色对当前写作有用}

---

## ✍️ 技法参考

### {technique}
📚 范例：{novel_name} — {scene_title}
> {summary}
💡 效果：{reader_effect}

---

📊 共找到 {n} 个场景参考、{m} 个人物参考、{k} 个技法参考
```

## 被 novel 项目调用的场景

此 skill 设计为被 `../novel` 项目的以下 skill 间接消费：

| novel 项目 skill | 使用方式 |
|-----------------|---------|
| `chapter-draft` | 在起草前检索类似场景作为参考 |
| `plot-suggest` | 检索相似结构/转折/套路的案例 |
| `inspiration-log` | 记录灵感时追溯素材来源 |

调用路径：`novel` skill → `python ../novel-material/scripts/core/search.py` → 获取精简结果 → 按需读场景 YAML 详情

## 注意事项

- 结果中的「参考价值」字段是关键——不只是找到匹配，还要解释**为什么对当前写作有用**
- 人物参考侧重心理深度维度（fatal_flaw / misbelief / tragedy_trigger），这些是创作中最有启发的信息
- 如果上下文太模糊无法推断维度，直接向用户追问 1-2 个关键信息
- 技法参考优先返回 `reader_effect` 与需求匹配的案例
- 场景参考返回原文定位（`text_range`），方便用户追溯原文

## References

- [material-search-scene SKILL.md](../material-search-scene/SKILL.md)
- [character-index.schema.yaml](../../../docs/schemas/character-index.schema.yaml)
- [plot-index.schema.yaml](../../../docs/schemas/plot-index.schema.yaml)
- [AGENTS.md](../../AGENTS.md)
