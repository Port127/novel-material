# Novel Material V2 - Agent Map

独立的小说素材管理系统，为多个小说项目提供共享素材检索服务。

## Priorities

1. 用户当前请求
2. 本文件
3. `ARCHITECTURE.md`

## Quick Start

```bash
# ── 流水线 ──
python scripts/pipeline.py ingest [路径]       # 入库+格式清洗+章节切分
python scripts/pipeline.py analyze [material_id] # 大纲+世界观+人物+标签+章级分析
python scripts/pipeline.py full [路径]          # 完整流程（入库→分析→建索引）

# ── 检索 ──
python scripts/search/search_world.py "修仙类小说的力量体系"
python scripts/search/search_outline.py "修仙小说大纲，废柴逆袭"
python scripts/search/search_detail.py "悬疑类中段推进模式"
python scripts/search/search_chapter.py "开局困境写法" --limit 10
python scripts/search/search_character.py "导师型人物写法"
python scripts/search/search_event.py "雨中告别的写法"
```

## Skills

| Skill | 用途 |
|-------|------|
| `material-add` | 添加新素材入库 |
| `material-delete` | 删除素材+清理所有关联 |
| `material-import` | 导入外部已分析好的素材 |
| `pipeline-ingest` | 入库+格式清洗流水线 |
| `pipeline-analyze` | 分析流水线（大纲/世界观/人物/标签/章级） |
| `pipeline-finalize` | 收尾流水线（精调+同步数据库） |
| `search` | 统一检索入口（自动路由） |
| `refine` | 基于证据的精调（调整而非增量） |

## ID 规范

格式：`nm_{type}_{YYYYMMDD}_{random4}`

## 数据生命周期

```
原文文件 → 格式清洗 → 章节切分 → 章级分析(LLM) → Embedding → 写入数据库
    ↓           ↓          ↓          ↓             ↓          ↓
source.txt  format_report  chapter_index  chapters.yaml  向量数据  PostgreSQL
```

## 标签体系

标签从 `data/tags.yaml` 字典中选取，包含 600+ 标签值：

```
L0 频道层    → 男频 / 女频 / 中性                              (3)
L1 题材层    → 玄幻/仙侠/都市/历史/科幻/游戏/悬疑/言情/...       (20 一级)
L2 子题材层  → 东方玄幻/异世大陆/修真文明/都市异能/...           (100+ 二级)
L3 元素层    → 系统/重生/无敌/废柴逆袭/种田/穿越/...            (200+)
L4 风格层    → 热血/轻松/虐心/暗黑/搞笑/爽文/...                (50+)
```

## 硬规则

- MUST 使用 skills 执行操作
- MUST 素材 ID 遵循命名规范
- MUST 标签从 `data/tags.yaml` 字典中选取
- MUST 以章节为最小分析单元，不进行事件/场景拆分
- MUST 章级分析写入后执行质量校验（摘要长度、标签合法性）
- MUST Embedding 写入后执行维度校验
- MUST 检索调用 `scripts/search/` 下的脚本
- MUST YAML 文件作为 Source of Truth，数据库是派生查询层
- NEVER 拆分事件（边界不可控）
- NEVER 标注结构角色（转折/高潮定义模糊）
- NEVER 用关键词匹配代替 LLM 理解
- NEVER 绕过质量门控

## 目录结构

```
├── scripts/                    # 脚本（core/analyze/search/utils）
├── data/                       # 数据（novels/ 索引/标签字典）
├── docs/                       # 文档（schemas/tag-system/research）
├── config/                     # 配置文件（database/llm/embedding）
└── .agents/skills/             # Agent Skills
```
