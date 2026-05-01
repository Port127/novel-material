# search

统一检索入口，根据查询意图路由到具体脚本。

## 当前状态

> ⚠️ 所有检索脚本当前**未实现 CLI 参数解析**（缺陷 C8）。
> 下方的命令行格式是**目标接口**，当前需要修改源码中的函数调用参数或通过 Python import 调用。

## 目标命令行格式（待实现）

```bash
python scripts/search/search_world.py "修仙类力量体系"
python scripts/search/search_outline.py "修仙大纲"
python scripts/search/search_detail.py "中段推进"
python scripts/search/search_chapter.py "开局困境" --genre 修仙 --limit 10
python scripts/search/search_character.py "导师型人物"
python scripts/search/search_event.py "雨中告别"
```

## 当前实际调用方式

```python
# 在 Python 中 import 调用
from scripts.search.search_chapter import search_chapters
search_chapters(query="开局困境写法", genre="修仙", limit=10)

from scripts.search.search_world import search_worldbuilding
search_worldbuilding(entity_type="faction", genre="修仙", limit=10)
```

## 检索类型与路由

Agent 应根据用户的查询意图，选择对应的检索脚本：

| 用户意图 | 脚本 | 函数 | 返回内容 |
|----------|------|------|----------|
| 世界观/力量体系/势力 | `search_world.py` | `search_worldbuilding()` | 世界观设定实体 |
| 全书大纲/结构 | `search_outline.py` | `search_outlines()` | 大纲结构树 |
| 序列/节拍级细纲 | `search_detail.py` | `search_details()` | 序列+节拍信息 |
| 章节写法/章纲 | `search_chapter.py` | `search_chapters()` | 章节摘要+功能标签+张力 |
| 人物塑造/出场 | `search_character.py` | `search_characters()` | 人物小传+出场统计 |
| 事件/场景写法 | `search_event.py` | `search_events()` | 匹配章节摘要+上下文 |

## 前置条件

- 数据库已初始化（`python scripts/core/init_db.py`）
- 至少有一本小说已完成 `pipeline.py finalize`（数据已同步到 DB）
- `.env` 中 `DATABASE_URL` 配置正确

## 路由判断指南

当用户的查询比较模糊时，Agent 应按以下优先级判断：

1. 如果提到"力量体系/势力/地图/规则" → `search_world`
2. 如果提到"大纲/结构/三幕" → `search_outline`
3. 如果提到"开局/第N章/写法" → `search_chapter`
4. 如果提到"人物/角色/导师/反派" → `search_character`
5. 如果提到具体事件（"告别/打斗/突破"） → `search_event`
6. 如果提到"节拍/序列/推进模式" → `search_detail`
