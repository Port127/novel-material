---
name: material-search
description: 素材库统一检索入口；根据查询自动路由到素材级、事件级或写作上下文检索
---

# 任务

作为素材库的**统一入口检索 skill**，根据用户输入自动选择最合适的检索路径。

## 边界

用于：
- 用户只说“帮我找素材 / 找参考”
- 不确定应该走素材检索、事件检索还是上下文检索

不用于：
- 替代 `material-search-event` 的精确标签检索逻辑
- 替代 `material-search-context` 的创作上下文推断逻辑

## 输入

- 关键词
- 书名 / 作者
- 角色名
- 事件需求
- 写作上下文描述

## 路由规则

| 输入特征 | 路由 |
|----------|------|
| 书名 / 作者 / 素材名 | 素材级匹配 |
| 角色名 | 先人物索引，再补事件检索 |
| 明显的事件需求 | `material-search-event` |
| 明显的写作上下文 / 创作问题 | `material-search-context` |
| 混合查询 | 先素材级缩范围，再转事件级 |

## 默认执行路径

### 1. 优先做路由判断

如果已经明显属于下游 skill 的输入类型，直接路由，不在这里重复做一套检索。

### 2. 素材级匹配

素材级检索时：

- 读取 `data/index.yaml`
- 必要时读取对应小说的 `tags.yaml`
- 返回素材名、作者、状态、风格 / 基调摘要

### 3. 事件级兜底

只有在不适合直接路由，或用户输入本身就是混合查询时，才在本 skill 内补做事件级检索。

事件级检索遵循三级回退：

1. `scripts/core/search.py`
2. YAML 倒排索引
3. 遍历事件文件

### 4. 返回结果

结果按“最有用”而不是“最早命中”排序。

## 输出要求

至少输出：

- 当前采用的检索路径
- 返回了素材级还是事件级结果
- 如已自动转到下游 skill，要在结果里说明

## 关键硬约束

- 检索优先走 `scripts/core/search.py`
- 不直接把大索引文件整份读进上下文
- material-search 负责路由，不和下游 skill 重复抢入口语义

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/router.md`
- `../material-search-event/SKILL.md`
- `../material-search-context/SKILL.md`
- `../../../ARCHITECTURE.md`
- `../../../AGENTS.md`
