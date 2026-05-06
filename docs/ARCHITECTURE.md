# Novel Material V2 - 系统架构

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Novel Material V2                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│  │ 原始文本    │ →  │ 入库流水线  │ →  │ YAML 存储   │                   │
│  │ (.txt)      │    │ ingest.py   │    │ data/novels │                   │
│  └─────────────┘    └─────────────┘    └─────────────┘                   │
│                            │                   │                         │
│                            ↓                   ↓                         │
│                     ┌─────────────┐    ┌─────────────┐                   │
│                     │ 分析流水线  │    │ 检索服务    │                   │
│                     │ pipeline.py │    │ search_*.py │                   │
│                     └─────────────┘    └─────────────┘                   │
│                            │                   │                         │
│                            ↓                   ↓                         │
│                     ┌─────────────────────────────────┐                  │
│                     │      PostgreSQL + pgvector      │                  │
│                     │  novels / chapters / tags / ... │                  │
│                     └─────────────────────────────────┘                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 数据流

### 入库阶段（无 LLM）

```
原始文本 → 预处理 → 章节切分 → YAML 存储
   │          │          │          │
   │      清洗广告      正则匹配   meta.yaml
   │      统一编码      重建边界   chapter_index.yaml
   │      检测章节      生成索引   source.txt
```

### 分析阶段（LLM 调用）

```
章级分析 → 向量化 → 骨架分析 → 精调 → 同步数据库
    │         │         │        │         │
    │      embedding  outline   统计     PostgreSQL
    │      (OpenAI)   worldbuild 出场次数  novels
    │                 characters 钩子数   chapters
    │                 tags                characters
    │                                     worldbuilding
```

## 核心模块

### 1. 入库模块 (`scripts/core/`)

| 文件 | 功能 |
|------|------|
| `ingest.py` | 入库入口：预处理 + 章节切分 |
| `preprocess.py` | 文本清洗：广告移除、编码统一 |
| `chapter_analyze.py` | LLM 章级分析（每章调用一次 API） |
| `embed_chapters.py` | 向量化：生成 `summary_embedding` |
| `sync_db.py` | YAML → PostgreSQL 同步 |
| `llm_client.py` | 统一 LLM 调用客户端（含重试） |

### 2. 分析模块 (`scripts/analyze/`)

| 文件 | 功能 | 容错策略 |
|------|------|---------|
| `generate_outline.py` | 大纲：幕/序列/节拍 | 3层容错 + `generate_simple_acts` 兜底 |
| `generate_worldbuilding.py` | 世界观：势力/地理/力量体系 | 空结构兜底 |
| `generate_characters.py` | 人物：档案/关系网 | 空列表兜底 |
| `generate_tags.py` | 标签：动态加载 + 分级审核 | 默认标签兜底 |

### 3. 检索模块 (`scripts/search/`)

| 文件 | 功能 | 搜索方式 |
|------|------|---------|
| `search_chapter.py` | 章节检索 | 向量语义 + 关键词 |
| `search_world.py` | 世界观检索 | 数据库查询 |
| `search_outline.py` | 大纲检索 | 数据库查询 |
| `search_character.py` | 人物检索 | 数据库查询 |
| `search_event.py` | 事件检索 | 向量语义 + 关键词 |

### 4. 标签模块 (`scripts/tags/`)

| 文件 | 功能 |
|------|------|
| `load.py` | 动态加载：按题材加载相关标签（600+ → ~100） |
| `validate.py` | 校验：检查标签是否在字典中 + 同义词映射 |
| `manage.py` | CLI 管理：add/remove/move/export |
| `review.py` | 审核：新标签候选审批 |
| `scheduled.py` | 批处理：频率自动批 + LLM 辅助审核 |

## 数据库表结构

### 核心表

```sql
-- 小说元信息
novels (
  material_id TEXT PRIMARY KEY,
  name TEXT,
  genre TEXT[],
  premise TEXT,
  chapter_count INTEGER,
  tags JSONB
)

-- 章节分析
chapters (
  material_id TEXT,
  chapter INTEGER,
  title TEXT,
  summary TEXT,
  tension_level INTEGER,
  chapter_functions TEXT[],
  characters_appear TEXT[],
  summary_embedding vector(1024)
)

-- 大纲结构
outline_sequences (
  material_id TEXT,
  act INTEGER,
  sequence INTEGER,
  title TEXT,
  chapters_start INTEGER,
  chapters_end INTEGER
)

outline_beats (
  material_id TEXT,
  act INTEGER,
  sequence INTEGER,
  beat INTEGER,
  title TEXT,
  chapter INTEGER,
  tension INTEGER
)

-- 人物档案
characters (
  material_id TEXT,
  name TEXT,
  role TEXT,
  archetype TEXT,
  arc_summary TEXT,
  psychology JSONB
)

-- 世界观
worldbuilding_entities (
  material_id TEXT,
  entity_type TEXT,
  name TEXT,
  importance TEXT,
  description TEXT
)
```

### 标签表

```sql
-- 标签字典（唯一数据源）
tags (
  dimension VARCHAR(50),   -- element/setting/style/structure
  tag VARCHAR(100),
  domain VARCHAR(50),      -- xuanhuan/xianxia/common/...
  synonym_of VARCHAR(100)  -- 同义词指向
)

-- 题材领域映射
genre_domain_map (
  genre_primary VARCHAR(50),
  domains JSONB            -- {"element": ["common", "xuanhuan"]}
)

-- 新标签候选（待审核）
new_tag_candidates (
  dimension VARCHAR(50),
  tag VARCHAR(100),
  occurrence_count INTEGER,
  status VARCHAR(20)       -- pending/auto_approved/approved/rejected
)
```

## 容错机制

### LLM 调用容错

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LLM 调用容错策略                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. 网络错误（429/5xx/超时）                                              │
│     └─ 指数退避重试（最多 8 次）                                          │
│     └─ 429 优先读取 Retry-After 响应头                                   │
│                                                                          │
│  2. 参数错误（context_length_exceeded）                                  │
│     └─ 快速失败，不重试（避免浪费时间）                                   │
│     └─ 立即抛出，由上层容错处理                                           │
│                                                                          │
│  3. 分析脚本容错                                                          │
│     ├─ generate_outline: 3层（前提/幕序列/beats）+ 兜底函数              │
│     ├─ generate_worldbuilding: 空结构兜底                                │
│     ├─ generate_characters: 空列表兜底                                   │
│     ├─ generate_tags: 默认标签兜底                                       │
│     └─ 结果：流程不中断，使用默认值继续                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 断点续传

章级分析采用断点续传机制：

```
已分析章节 → chapters/{n:04d}.yaml（独立文件）
    ↓
任意章节失败 → 跳过，继续下一章
    ↓
崩溃恢复 → 从 max(done.keys()) + 1 继续
    ↓
全部完成 → 合并为 chapters.yaml
```

## 标签分级系统

### 动态加载

```
用户题材: 玄幻
    ↓
查询 genre_domain_map → {"element": ["common", "xuanhuan"]}
    ↓
加载 tags 表 → 约 100 个标签（而非 600+）
    ↓
精简 LLM prompt → 避免截断
```

### 分级审核

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        新标签入库分级策略                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Level 0 - 自动入库                                                       │
│  ├─ hooks / tropes / themes / genre_description                         │
│  └─ 统计到 free_tags_stats 表                                            │
│                                                                          │
│  Level 1 - 频率自动批（出现 ≥3 次）                                       │
│  ├─ element / style                                                      │
│  └─ scheduled.py auto_approve_by_frequency()                            │
│                                                                          │
│  Level 2 - LLM 辅助审核                                                   │
│  ├─ setting / structure                                                  │
│  └─ scheduled.py llm_batch_review()                                      │
│                                                                          │
│  Level 3 - 人工审核                                                       │
│  ├─ genre_primary / genre_secondary                                      │
│  └─ review.py approve-genre / reject                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 检索架构

### 向量检索

```
查询文本 → Embedding API → 查询向量
    ↓
PostgreSQL pgvector → cosine_similarity
    ↓
返回相似度最高的 N 条结果
```

### 标签领域定位

```
检索参数: --element 血脉
    ↓
resolve_tag_domain("element", "血脉")
    ↓
返回: ("xuanhuan", False)  // 非通用标签
    ↓
建议: --genre 玄幻（获得更精准结果）
```