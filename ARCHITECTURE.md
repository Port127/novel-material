# Novel Material V2 - 系统架构

本文档描述系统的真实架构、数据流向和模块边界。

## 相关文档

- [REQUIREMENTS.md](docs/REQUIREMENTS.md) — 业务边界与不做什么（为什么这样设计）
- [USER_MANUAL.md](docs/USER_MANUAL.md) — 详细使用手册（如何使用）
- [AGENTS.md](AGENTS.md) — Agent 操作规则
- [README.md](README.md) — 项目入口与快速开始

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Novel Material V2                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │ 原始文本    │ →  │ CLI 入口    │ →  │ YAML 存储   │                      │
│  │ (.txt)      │    │ nm          │    │ data/novels │                      │
│  └─────────────┘    └─────────────┘    └─────────────┘                      │
│                            │                   │                            │
│                            ↓                   ↓                            │
│                     ┌─────────────┐    ┌─────────────┐                      │
│                     │ Pipeline    │    │ Search      │                      │
│                     │ (pipeline/) │    │ (search/)   │                      │
│                     └─────────────┘    └─────────────┘                      │
│                            │                   │                            │
│                            ↓                   ↓                            │
│                     ┌─────────────┐    ┌─────────────┐                      │
│                     │ Tags        │    │ Validation  │                      │
│                     │ (tags/)     │    │ (validation/)│                      │
│                     └─────────────┘    └─────────────┘                      │
│                            │                   │                            │
│                            ↓                   ↓                            │
│                     ┌─────────────────────────────────┐                     │
│                     │      PostgreSQL + pgvector      │                     │
│                     │  novels / chapters / tags / ... │                     │
│                     └─────────────────────────────────┘                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 目录结构

```
novel-material/
├── src/novel_material/           # 核心代码
│   ├── cli/                      # CLI 入口 (nm)
│   │   ├── main.py               # 主入口：注册所有子命令
│   │   ├── pipeline.py           # 流水线命令：ingest/analyze/outline/refine/...
│   │   ├── search.py             # 检索命令：chapter/outline/character/world
│   │   ├── tags.py               # 标签管理：stats/list/add/remove/review
│   │   ├── material.py           # 素材管理：list/import/delete
│   │   ├── storage.py            # 数据库管理：init/sync/reset
│   │   └── validate.py           # 校验命令：schema/quality
│   ├── pipeline/                 # 流水线逻辑
│   │   ├── ingest.py             # 入库：预处理 + 章节切分
│   │   ├── preprocess.py         # 文本清洗：NFC归一化/去广告/数字转换
│   │   ├── loader.py             # 章节数据加载 + 摘要池构建
│   │   ├── analyze.py            # 章级分析：摘要/张力/人物/功能
│   │   ├── outline.py            # 大纲生成：三幕结构 + 序列节拍
│   │   ├── worldbuilding.py      # 世界观提取：势力/地域/体系
│   │   ├── characters.py         # 人物提取：原型/弧线/心理
│   │   ├── tags.py               # 标签生成：element/style/structure
│   │   ├── refine.py             # 统计精调：出场次数/钩子数
│   │   └── progress.py           # 进度跟踪 + 断点检测
│   ├── search/                   # 检索逻辑
│   │   ├── chapter.py            # 章节检索：向量语义搜索
│   │   ├── outline.py            # 大纲检索：题材/前提筛选
│   │   ├── character.py          # 人物检索：原型/角色定位
│   │   ├── world.py              # 世界观检索：维度筛选
│   │   ├── event.py              # 事件检索：场景/情绪过滤
│   │   ├── detail.py             # 细节检索（内部模块，未暴露 CLI 入口）
│   │   └── common.py             # 共享工具：关键词提取/数据库连接
│   ├── storage/                  # 数据库层
│   │   ├── init_db.py            # 表结构初始化
│   │   ├── init_data.py          # 基础数据初始化（genre_domain_map）
│   │   ├── init_tags.py          # 标签字典导入
│   │   ├── sync.py               # YAML → PostgreSQL 同步
│   │   ├── embedding.py          # 向量化存储
│   │   └── schema.sql            # DDL 定义（外部引用）
│   ├── tags/                     # 标签系统
│   │   ├── load.py               # 动态加载：按题材加载相关标签
│   │   ├── validate.py           # 校验 + 同义词映射
│   │   ├── resolve.py            # 标签领域定位
│   │   ├── export_view.py        # YAML 视图导出
│   │   └── scheduled.py          # 批处理审核
│   ├── infra/                    # 基础设施
│   │   ├── config.py             # 配置加载（settings.yaml）
│   │   ├── llm.py                # LLM 调用客户端（多服务商）
│   │   ├── embedding.py          # Embedding API
│   │   ├── progress.py           # 进度跟踪
│   │   └── logging_config.py     # 日志配置
│   ├── validation/               # 校验层
│   │   ├── schema.py             # YAML Schema 校验（pydantic）
│   │   ├── quality.py            # 内容质量校验
│   │   └── tag_rules.py          # 标签规则
│   └── material/                 # 素材管理
│       ├── import_material.py    # 导入外部素材
│       └── delete.py             # 删除素材
├── data/                         # 数据目录
│   ├── novels/                   # 素材存储
│   │   └── nm_novel_YYYYMMDD_xxxx/
│   │       ├── source.txt        # 清洗后原文
│   │       ├── meta.yaml         # 元信息
│   │       ├── chapter_index.yaml  # 章节索引
│   │       ├── chapters.yaml     # 章级分析合并
│   │       ├── chapters/         # 章级分析（独立文件，断点续传）
│   │       ├── outline/          # 大纲结构
│   │       │   ├── structure.yaml
│   │       │   ├── plotlines.yaml
│   │       │   ├── hooks_network.yaml
│   │       │   └── _index.yaml   # 大纲索引
│   │       ├── characters/       # 人物档案
│   │       │   ├── profiles/*.yaml
│   │       │   └── relations.yaml
│   │       ├── worldbuilding/    # 世界观
│   │       │   ├── factions.yaml
│   │       │   ├── regions.yaml
│   │       │   ├── power_systems.yaml
│   │       │   └── _index.yaml
│   │       ├── tags.yaml         # 小说级标签
│   │       ├── chapter_embeddings.npz  # 向量缓存
│   │       └── pipeline.log      # 流水线日志
│   ├── schemas/                  # YAML Schema 定义
│   └── tag-system/               # 标签分类学文档
├── config/                       # 配置目录
│   ├── settings.yaml             # 主配置文件
│   └── providers.yaml            # 多服务商配置
├── .claude/skills/               # Agent Skills
├── docs/                         # 文档
├── tests/                        # 测试
├── Makefile                      # Docker 管理
└── pyproject.toml                # Python 包配置
```

## 数据流

### 入库阶段（无 LLM）

```
原始文本 → 预处理 → 章节切分 → 类型识别 → YAML 存储
   │          │          │          │          │
   │      NFC 归一化   正则匹配   章节类型   meta.yaml
   │      去广告水印   边界重建   normal/    chapter_index.yaml
   │      数字转换     索引生成   afterword  source.txt
   │                                extra      status: clean
   │                                author_note
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
    │                                     outline_sequences
    │                                     outline_beats
```

### 断点续传机制

```
章级分析 → chapters/{n:04d}.yaml（独立文件）
    ↓
任意章节失败 → 跳过，继续下一章
    ↓
崩溃恢复 → 从 max(done.keys()) + 1 继续
    ↓
全部完成 → 合并为 chapters.yaml + 删除独立文件
```

## 核心模块详解

### CLI 层 (`cli/`)

| 命令 | 功能 | 底层调用 |
|------|------|---------|
| `nm pipeline ingest` | 入库 | `pipeline/ingest.py` |
| `nm pipeline analyze` | 章级分析 | `pipeline/analyze.py` |
| `nm pipeline outline` | 大纲生成 | `pipeline/outline.py` |
| `nm pipeline worldbuilding` | 世界观提取 | `pipeline/worldbuilding.py` |
| `nm pipeline characters` | 人物提取 | `pipeline/characters.py` |
| `nm pipeline tags` | 标签生成 | `pipeline/tags.py` |
| `nm pipeline refine` | 精调同步 | `pipeline/refine.py` + `storage/sync.py` |
| `nm pipeline full` | 完整流水线 | 组合调用 |
| `nm pipeline continue` | 断点续传 | `pipeline/progress.py` + 组合调用 |
| `nm search chapter` | 章节检索 | `search/chapter.py` |
| `nm search outline` | 大纲检索 | `search/outline.py` |
| `nm search character` | 人物检索 | `search/character.py` |
| `nm search world` | 世界观检索 | `search/world.py` |
| `nm search event` | 事件检索 | `search/event.py` |
| `nm tags stats` | 标签统计 | 数据库查询 |
| `nm tags list` | 标签列表 | 数据库查询 |
| `nm tags add` | 添加标签 | 数据库写入 |
| `nm storage init-db` | 初始化表 | `storage/init_db.py` |
| `nm storage sync` | 数据库同步 | `storage/sync.py` |
| `nm validate schema` | Schema 校验 | `validation/schema.py` |

### Pipeline 层 (`pipeline/`)

| 模块 | 功能 | 容错策略 |
|------|------|---------|
| `ingest.py` | 入库 | 失败返回 None |
| `preprocess.py` | 文本清洗 | 无 LLM，纯本地逻辑 |
| `loader.py` | 数据加载 | 加载失败时返回空结构 |
| `analyze.py` | 章级分析 | 断点续传 + 跳过失败章节 + 特殊章节类型识别 |
| `outline.py` | 大纲生成 | 3层容错 + `generate_simple_acts` 兜底 |
| `worldbuilding.py` | 世界观提取 | 空结构兜底 |
| `characters.py` | 人物提取 | 空列表兜底 |
| `tags.py` | 标签生成 | 默认标签兜底 |
| `refine.py` | 统计精调 | 增量更新 |
| `progress.py` | 进度跟踪 | 检测各阶段完成状态 |

### Search 层 (`search/`)

| 模块 | 功能 | 搜索方式 |
|------|------|---------|
| `chapter.py` | 章节检索 | 向量语义 + 关键词 |
| `outline.py` | 大纲检索 | 题材/前提筛选 |
| `character.py` | 人物检索 | 原型/角色定位筛选 |
| `world.py` | 世界观检索 | 维度筛选 + 关键词 |
| `event.py` | 事件检索 | 向量语义 + 场景/情绪过滤 |
| `detail.py` | 细节检索 | 内部模块，未暴露 CLI 入口 |
| `common.py` | 共享工具 | 关键词提取/数据库连接 |

### Storage 层 (`storage/`)

| 模块 | 功能 |
|------|------|
| `init_db.py` | 执行 schema.sql 创建表 |
| `init_data.py` | 初始化 genre_domain_map 映射表 |
| `init_tags.py` | 导入标签字典（如 data/tags.yaml 存在） |
| `sync.py` | YAML → PostgreSQL 同步（含 Schema 预检） |
| `embedding.py` | 章节摘要向量化存储 |

### Tags 层 (`tags/`)

| 模块 | 功能 |
|------|------|
| `load.py` | 动态加载：按题材加载相关标签（600+ → ~100） |
| `validate.py` | 校验标签合法性 + 同义词映射 |
| `resolve.py` | 标签领域定位（检测标签属于哪个领域） |
| `export_view.py` | CLI 管理：导出人读格式 YAML |
| `scheduled.py` | 新标签候选审批（频率自动批） |

### Validation 层 (`validation/`)

| 模块 | 功能 |
|------|------|
| `schema.py` | Pydantic 结构校验：meta/chapters/tags |
| `quality.py` | 内容质量校验：摘要长度/张力合理性 |
| `tag_rules.py` | 标签规则校验 |

### Infra 层 (`infra/`)

| 模块 | 功能 |
|------|------|
| `config.py` | 配置加载（settings.yaml + 环境变量） |
| `llm.py` | LLM 调用客户端（多服务商 + 重试 + 统计） |
| `embedding.py` | Embedding API 调用 |
| `progress.py` | 进度跟踪（SilentConsole + PipelineLogger） |

## 数据库表结构

### 核心表

```sql
-- 小说元信息
novels (
  material_id TEXT PRIMARY KEY,
  name TEXT,
  author TEXT,
  genre TEXT[],
  word_count INTEGER,
  chapter_count INTEGER,
  status TEXT,
  premise TEXT,
  theme TEXT[],
  tone TEXT[],
  act_count INTEGER,
  sequence_count INTEGER,
  hook_count INTEGER,
  subplot_count INTEGER,
  structure_type TEXT,
  tags JSONB,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)

-- 章节分析
chapters (
  material_id TEXT,
  chapter INTEGER,
  title TEXT,
  chapter_type TEXT,        -- normal/afterword/extra/author_note
  summary TEXT,
  word_count INTEGER,
  tension_level INTEGER,
  pacing TEXT,
  setting TEXT[],
  key_plot_point TEXT,
  chapter_functions TEXT[],
  characters_appear TEXT[],
  summary_embedding vector(4096),
  PRIMARY KEY (material_id, chapter)
)

-- 大纲序列
outline_sequences (
  material_id TEXT,
  act INTEGER,
  sequence INTEGER,
  title TEXT,
  description TEXT,
  chapters_start INTEGER,
  chapters_end INTEGER,
  PRIMARY KEY (material_id, act, sequence)
)

-- 大纲节拍
outline_beats (
  material_id TEXT,
  act INTEGER,
  sequence INTEGER,
  beat INTEGER,
  title TEXT,
  description TEXT,
  chapter INTEGER,
  tension INTEGER,
  PRIMARY KEY (material_id, act, sequence, beat)
)

-- 人物
characters (
  material_id TEXT,
  name TEXT,
  role TEXT,
  archetype TEXT,
  moral_spectrum TEXT,
  arc_summary TEXT,
  narrative_function TEXT,
  psychology JSONB,
  first_appearance INTEGER,
  last_appearance INTEGER,
  appearance_count INTEGER,
  description TEXT,
  file_path TEXT,
  PRIMARY KEY (material_id, name)
)

-- 人物出场记录
character_appearances (
  material_id TEXT,
  character_name TEXT,
  chapter INTEGER,
  significance TEXT
)

-- 世界观实体
worldbuilding_entities (
  material_id TEXT,
  entity_type TEXT,
  name TEXT,
  importance TEXT,
  description TEXT,
  properties JSONB,
  first_appearance INTEGER,
  PRIMARY KEY (material_id, entity_type, name)
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
  description TEXT,
  created_at TIMESTAMP,
  PRIMARY KEY (dimension, tag)
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
  status VARCHAR(20),       -- pending/approved/rejected
  created_at TIMESTAMP
)
```

## 容错机制

### LLM 调用容错

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LLM 调用容错策略                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  网络错误（429/5xx/超时）                                                     │
│  ├─ 指数退避重试（最多 8 次）                                                 │
│  ├─ 429 优先读取 Retry-After 响应头                                          │
│  └─ 总超时控制（含所有重试）                                                  │
│                                                                              │
│  参数错误（context_length_exceeded）                                         │
│  ├─ 快速失败，不重试                                                          │
│  └─ 立即抛出，由上层容错处理                                                  │
│                                                                              │
│  JSON 解析失败                                                                │
│  ├─ 自动翻倍 max_tokens 重试（最多 2 次）                                     │
│  └─ 上限 65536 tokens                                                        │
│                                                                              │
│  分析脚本容错                                                                 │
│  ├─ outline: 3层容错 + generate_simple_acts() 兜底                           │
│  ├─ worldbuilding: 空结构兜底                                                 │
│  ├─ characters: 空列表兜底                                                    │
│  ├─ tags: 默认标签兜底                                                        │
│  └─ 结果：流程不中断，使用默认值继续                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
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

## 配置系统

### 配置优先级

1. `config/providers.yaml`（多服务商配置）
2. `config/settings.yaml`（主配置）
3. `.env` 环境变量
4. 默认值

### 多服务商支持

```yaml
# config/providers.yaml
default_provider: deepseek
providers:
  - name: deepseek
    model: deepseek-chat
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    thinking_format: openai  # 标准 OpenAI 格式
  - name: qwen
    model: qwen3.6-plus
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    thinking_format: dashscope  # 阿里云 DashScope 格式
```

通过 `--provider` 参数切换服务商：
```bash
nm pipeline analyze nm_xxx --provider qwen
```

## 日志系统

### 日志文件

- `data/novels/{material_id}/pipeline.log`：流水线执行日志
- 包含：API 调用详情、错误分类、重试状态

### 日志格式

```
[章节分析#批次53] API: 12.3s | in=4521 out=823 total=5344 | thinking=1200 | finish=stop | req=abc123...
[RATE] 重试 3/8，等待 60s: RateLimitError
```

### 错误分类标签

| 标签 | 含义 |
|------|------|
| `[AUTH]` | 认证错误（API Key 无效） |
| `[RATE]` | 速率限制（429） |
| `[SERVER]` | 服务端错误（5xx） |
| `[TIMEOUT]` | 超时错误 |
| `[CONN]` | 连接错误 |
| `[JSON]` | JSON 解析失败 |
| `[HTTP]` | 其他 HTTP 错误 |