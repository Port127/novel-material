---
name: search
description: 统一检索入口，根据查询意图路由到具体检索脚本。当用户需要检索世界观、大纲、章节、人物或事件数据时使用。支持向量语义搜索。
---

# search

统一检索入口，根据查询意图路由到具体检索脚本。

## 执行命令

所有检索脚本已实现 CLI 参数解析（使用 click）：

```bash
# 章节检索（支持语义搜索）
python scripts/search/search_chapter.py "开局困境" --genre 修仙 --limit 10
python scripts/search/search_chapter.py "主角突破" --semantic  # 向量语义搜索

# 世界观检索
python scripts/search/search_world.py "修仙类力量体系"
python scripts/search/search_world.py "" --type factions --genre 修仙

# 大纲检索
python scripts/search/search_outline.py "修仙大纲"

# 序列/节拍检索
python scripts/search/search_detail.py "中段推进"

# 人物检索
python scripts/search/search_character.py "导师型人物"

# 事件检索
python scripts/search/search_event.py "雨中告别"
```

## 检索类型与路由

Agent 应根据用户的查询意图，选择对应的检索脚本：

| 用户意图 | 脚本 | 主要参数 | 返回内容 |
|----------|------|------|----------|
| 世界观/力量体系/势力 | `search_world.py` | `--type/--genre/--importance` | 世界观设定实体 |
| 全书大纲/结构 | `search_outline.py` | `--genre/--limit` | 大纲结构树 |
| 序列/节拍级细纲 | `search_detail.py` | `--genre/--limit` | 序列+节拍信息 |
| 章节写法/章纲 | `search_chapter.py` | `--genre/--function/--semantic` | 章节摘要+功能标签+张力 |
| 人物塑造/出场 | `search_character.py` | `--genre/--role/--limit` | 人物小传+出场统计 |
| 事件/场景写法 | `search_event.py` | `--genre/--limit` | 匹配章节摘要+上下文 |

## 前置条件

- 数据库已初始化（`python scripts/core/init_db.py`）
- 至少有一本小说已完成 `pipeline.py finalize`（数据已同步到 DB）
- `.env` 中 `DATABASE_URL` 配置正确

## 路由判断指南

当用户的查询比较模糊时，按以下优先级判断：

1. 如果提到"力量体系/势力/地图/规则" → `search_world`
2. 如果提到"大纲/结构/三幕" → `search_outline`
3. 如果提到"开局/第N章/写法" → `search_chapter`
4. 如果提到"人物/角色/导师/反派" → `search_character`
5. 如果提到具体事件（"告别/打斗/突破"） → `search_event`
6. 如果提到"节拍/序列/推进模式" → `search_detail`

## 语义搜索

章节检索支持向量语义搜索（`--semantic`），使用 `summary_embedding` 字段进行余弦距离匹配，比关键词匹配更精准。