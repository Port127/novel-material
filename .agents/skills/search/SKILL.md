# search

统一检索入口，根据查询类型自动路由到具体脚本。

## 用法

```bash
# 各类型独立脚本
python scripts/search/search_world.py "修仙类力量体系"
python scripts/search/search_outline.py "修仙大纲"
python scripts/search/search_detail.py "中段推进"
python scripts/search/search_chapter.py "开局困境" --genre 修仙 --limit 10
python scripts/search/search_character.py "导师型人物"
python scripts/search/search_event.py "雨中告别"
```

## 检索类型

| 类型 | 脚本 | 返回内容 |
|------|------|----------|
| world | search_world.py | 世界观设定（势力/地理/力量体系） |
| outline | search_outline.py | 完整大纲结构树 |
| detail | search_detail.py | 序列+节拍级细纲 |
| chapter | search_chapter.py | 章节摘要+功能标签+结构信息 |
| character | search_character.py | 人物小传+出场信息 |
| event | search_event.py | 匹配的章节摘要+上下文 |
