---
name: material-search-event
description: 将自然语言事件需求解析为标签组合，并按多维条件检索匹配事件
---

# 任务

把自然语言需求映射成标签条件，检索事件级参考素材。

这是**精确事件检索**入口，不负责写作上下文的扩展推断。

## 边界

用于：
- “弱者反杀强者”
- “雨中告别”
- “恋人争吵但最后没分手”

不用于：
- 泛素材检索入口
- 大段创作上下文的综合参考

## 输入

- 自然语言需求描述

## 默认执行路径

### 1. 解析为标签组合

把输入映射到标签维度，例如：

- `event_type`
- `relationship`
- `interaction`
- `power_dynamic`
- `emotion`
- `reader_effect`
- `technique`

如存在多种合理解析，默认选最强主解释直接检索，不先停下来确认。

### 2. 优先使用脚本检索

先走：

```bash
python scripts/core/search.py event ...
```

能力包括：

- AND 交集
- 无结果时自动放宽
- 匹配度排序

### 3. 回退路径

脚本不可用时：

1. 查 `events_index.yaml`
2. 再必要时只读取命中 event YAML
3. 最后才遍历事件文件

### 4. 结果整理

返回时要说清楚：

- 命中了哪些标签
- 哪些是核心匹配
- 哪些是放宽条件后的次优匹配

## 输出要求

至少输出：

- 解析后的标签组合
- Top 结果
- 匹配标签与原文定位

## 关键硬约束

- 优先用 `search.py`
- 不要求用户先确认解析结果
- 无结果时先自动放宽一层，不直接报空

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/query-mapping.md`
- `../../../AGENTS.md`
