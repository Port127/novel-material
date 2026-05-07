---
name: search
description: 统一检索入口，根据查询意图路由到具体检索脚本。当用户需要检索世界观、大纲、章节、人物或事件数据时使用。支持向量语义搜索。
---

# search

统一检索入口，根据查询意图路由到具体检索命令。

## 执行命令

```bash
# 章节检索（支持语义搜索）
nm search chapter "开局困境" --limit 10

# 世界观检索
nm search world "势力" --dimension faction

# 大纲检索
nm search outline --genre 修仙 --query "废柴逆袭"

# 人物检索
nm search character --archetype 导师

# 事件检索
nm search event "雨中告别" --limit 10
```

## 检索类型与路由

Agent 应根据用户的查询意图，选择对应的检索命令：

| 用户意图 | 命令 | 主要参数 | 返回内容 |
|----------|------|------|----------|
| 世界观/力量体系/势力 | `nm search world` | `--dimension/--genre` | 世界观设定实体 |
| 全书大纲/结构 | `nm search outline` | `--genre/--limit` | 大纲结构树 |
| 章节写法/章纲 | `nm search chapter` | `--genre/--limit` | 章节摘要+功能标签+张力 |
| 人物塑造/出场 | `nm search character` | `--genre/--role/--limit` | 人物小传+出场统计 |

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