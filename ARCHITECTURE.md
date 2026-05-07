# Novel Material V2 - 系统架构

本文档描述系统的真实架构、数据流向和模块边界。

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Novel Material V2                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│  │ 原始文本    │ →  │ CLI 入口    │ →  │ YAML 存储   │                   │
│  │ (.txt)      │    │ nm pipeline │    │ data/novels │                   │
│  └─────────────┘    └─────────────┘    └─────────────┘                   │
│                            │                   │                         │
│                            ↓                   ↓                         │
│                     ┌─────────────┐    ┌─────────────┐                   │
│                     │ Pipeline    │    │ Search      │                   │
│                     │ (src/pipeline)│    │ (src/search)│                   │
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

## 目录结构

```
novel-material/
├── src/novel_material/       # 核心代码
│   ├── cli/                  # CLI 入口 (nm)
│   │   ├── main.py           # 主入口
│   │   ├── pipeline.py       # 流水线命令
│   │   ├── search.py         # 检索命令
│   │   ├── tags.py           # 标签管理
│   │   ├── material.py       # 素材管理
│   │   ├── storage.py        # 数据库管理
│   │   └── validate.py       # 校验命令
│   ├── pipeline/             # 流水线逻辑
│   │   ├── ingest.py         # 入库：预处理 + 章节切分
│   │   ├── preprocess.py     # 文本清洗
│   │   ├── analyze.py        # 章级分析
│   │   ├── outline.py        # 大纲生成
│   │   ├── worldbuilding.py  # 世界观提取
│   │   ├── characters.py     # 人物提取
│   │   ├── tags.py           # 标签生成
│   │   ├── refine.py         # 统计精调
│   │   └── loader.py         # 摘要池构建
│   ├── search/               # 检索逻辑
│   │   ├── chapter.py        # 章节检索
│   │   ├── world.py          # 世界观检索
│   │   ├── outline.py        # 大纲检索
│   │   ├── character.py      # 人物检索
│   │   ├── event.py          # 事件检索
│   │   └── common.py         # 公共工具
│   ├── storage/              # 数据库层
│   │   ├── init_db.py        # 表结构初始化
│   │   ├── init_data.py      # 基础数据初始化
│   │   ├── init_tags.py      # 标签字典导入
│   │   ├── sync.py           # YAML → PostgreSQL 同步
│   │   ├── embedding.py      # 向量化存储
│   │   └── schema.sql        # DDL 定义
│   ├── tags/                 # 标签系统
│   │   ├── load.py           # 动态加载（按题材）
│   │   ├── validate.py       # 校验 + 同义词映射
│   │   ├── manage.py         # CLI 管理
│   │   ├── review.py         # 新标签审核
│   │   ├── scheduled.py      # 批处理审核
│   │   └── export_view.py    # YAML 视图导出
│   ├── infra/                # 基础设施
│   │   ├── config.py         # 配置加载
│   │   ├── llm.py            # LLM 调用客户端
│   │   ├── embedding.py      # Embedding 调用
│   │   └── progress.py       # 进度跟踪
│   ├── validation/           # 校验层
│   │   ├── schema.py         # YAML Schema 校验
│   │   ├── quality.py        # 内容质量校验
│   │   └── tag_rules.py      # 标签规则
│   └── material/             # 素材管理
│   │   ├── import_material.py
│   │   └── delete.py
├── data/                     # 数据目录
│   ├── novels/               # 素材存储
│   │   └── nm_novel_YYYYMMDD_xxxx/
│   │       ├── source.txt
│   │       ├── meta.yaml
│   │       ├── chapters.yaml
│   │       ├── outline/
│   │       ├── characters/
│   │       ├── worldbuilding/
│   │       └── tags.yaml
│   ├── schemas/              # YAML Schema 定义
│   └── tag-system/           # 标签分类学文档
├── .claude/skills/           # Agent Skills
├── docs/                     # 文档
├── Makefile                  # Docker 管理
└── pyproject.toml            # Python 包配置
```

## 数据流

### 入库阶段（无 LLM）

```
原始文本 → 预处理 → 章节切分 → YAML 存储
   │          │          │          │
   │      NFC 归一化   正则匹配   meta.yaml
   │      去广告水印   边界重建   chapter_index.yaml
   │      数字转换     索引生成   source.txt
```

### 分析阶段（LLM 调用）

```
章级分析 → 向量化 → 骨架分析 → 精调 → 同步数据库
    │         │         │        │         │
    │      embedding  outline   统计     PostgreSQL
    │      (OpenAI)   world     出场次数  novels
    │                 characters 钩子数   chapters
    │                 tags                characters
    │                                     worldbuilding
```

## 核心模块详解

### CLI 层 (`cli/`)

| 命令 | 功能 | 底层调用 |
|------|------|---------|
| `nm pipeline ingest` | 入库 | `pipeline/ingest.py` |
| `nm pipeline full` | 完整流水线 | 组合调用 |
| `nm pipeline outline` | 大纲生成 | `pipeline/outline.py` |
| `nm pipeline refine` | 精调同步 | `pipeline/refine.py` + `storage/sync.py` |
| `nm search chapter` | 章节检索 | `search/chapter.py` |
| `nm tags stats` | 标签统计 | 数据库查询 |
| `nm storage init-db` | 初始化表 | `storage/init_db.py` |

### Pipeline 层 (`pipeline/`)

| 模块 | 功能 | 容错策略 |
|------|------|---------|
| `analyze.py` | 章级分析 | 断点续传 + 跳过失败章节 |
| `outline.py` | 大纲生成 | 3层容错 + `generate_simple_acts` 兜底 |
| `worldbuilding.py` | 世界观提取 | 空结构兜底 |
| `characters.py` | 人物提取 | 空列表兜底 |
| `tags.py` | 标签生成 | 默认标签兜底 |
| `refine.py` | 统计精调 | 增量更新 |

### Storage 层 (`storage/`)

| 模块 | 功能 |
|------|------|
| `init_db.py` | 执行 schema.sql 创建表 |
| `init_data.py` | 初始化 genre_domain_map |
| `init_tags.py` | 导入标签字典（如 data/tags.yaml 存在） |
| `sync.py` | YAML → PostgreSQL 同步 |
| `embedding.py` | 章节摘要向量化 |

### Tags 层 (`tags/`)

| 模块 | 功能 |
|------|------|
| `load.py` | 动态加载：按题材加载相关标签（600+ → ~100） |
| `validate.py` | 校验标签合法性 + 同义词映射 |
| `manage.py` | CLI 管理：add/remove/export |
| `review.py` | 新标签候选审批 |

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
  tags JSONB,
  status TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
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
  key_plot_point TEXT,
  summary_embedding vector(4096)
)

-- 大纲
outline_sequences (
  material_id TEXT,
  act INTEGER,
  sequence INTEGER,
  title TEXT,
  description TEXT,
  chapters_start INTEGER,
  chapters_end INTEGER
)

outline_beats (
  material_id TEXT,
  act INTEGER,
  sequence INTEGER,
  beat INTEGER,
  title TEXT,
  description TEXT,
  chapter INTEGER,
  tension INTEGER
)

-- 人物
characters (
  material_id TEXT,
  name TEXT,
  role TEXT,
  archetype TEXT,
  arc_summary TEXT,
  psychology JSONB,
  appearance_count INTEGER
)

character_appearances (
  material_id TEXT,
  character_name TEXT,
  chapter INTEGER,
  significance TEXT
)

-- 世界观
worldbuilding_entities (
  material_id TEXT,
  entity_type TEXT,
  name TEXT,
  importance TEXT,
  description TEXT,
  dimension TEXT
)
```

### 标签表

```sql
-- 标签字典（唯一数据源）
tags (
  dimension VARCHAR(50),    -- element/setting/style/structure
  tag VARCHAR(100),
  domain VARCHAR(50),       -- xuanhuan/xianxia/common/...
  group_name VARCHAR(100),
  is_common BOOLEAN,
  synonym_of VARCHAR(100),  -- 同义词指向
  description TEXT
)

-- 题材领域映射
genre_domain_map (
  genre_primary VARCHAR(50) PRIMARY KEY,
  domains JSONB             -- {"element": ["common", "xuanhuan"]}
)

-- 新标签候选
new_tag_candidates (
  id SERIAL,
  dimension VARCHAR(50),
  tag VARCHAR(100),
  occurrence_count INTEGER,
  source_material TEXT,
  status VARCHAR(20)        -- pending/approved/rejected
)
```

## 容错机制

### LLM 调用容错

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LLM 调用容错策略                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  网络错误（429/5xx/超时）                                                 │
│  ├─ 指数退避重试（最多 8 次）                                             │
│  ├─ 429 优先读取 Retry-After 响应头                                      │
│  └─ 总超时控制（含所有重试）                                              │
│                                                                          │
│  参数错误（context_length_exceeded）                                     │
│  ├─ 快速失败，不重试                                                      │
│  └─ 立即抛出，由上层容错处理                                              │
│                                                                          │
│  分析脚本容错                                                             │
│  ├─ outline: 3层容错 + generate_simple_acts() 兜底                       │
│  ├─ worldbuilding: 空结构兜底                                             │
│  ├─ characters: 空列表兜底                                                │
│  ├─ tags: 默认标签兜底                                                    │
│  └─ 结果：流程不中断，使用默认值继续                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 断点续传

```
章级分析 → chapters/{n:04d}.yaml（独立文件）
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

| Level | 标签类型 | 审核方式 |
|-------|---------|---------|
| 0 | hooks/tropes/themes | 自动入库 |
| 1 | element/style | 出现 ≥3 次自动批 |
| 2 | setting/structure | LLM 辅助审核 |
| 3 | genre | 人工审核 |

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
返回: ("xuanhuan", False)
    ↓
建议: --genre 玄幻（获得更精准结果）
```