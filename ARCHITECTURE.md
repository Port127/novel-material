# Novel Material V2 - 系统架构

本文档描述系统的真实架构、数据流向和模块边界。

## 相关文档

- [REQUIREMENTS.md](docs/REQUIREMENTS.md) — 业务边界与不做什么（为什么这样设计）
- [USER_MANUAL.md](docs/USER_MANUAL.md) — 详细使用手册（如何使用）
- [AGENTS.md](AGENTS.md) — Agent 操作规则
- [README.md](README.md) — 项目入口与快速开始

---

## 架构总览

### 设计理念

本项目采用**契约驱动设计**（Contract-Driven Design），核心原则：

1. **单一数据源**：所有校验阈值、提示词参数集中在 YAML 契约文件，一处修改多处生效
2. **服务层抽象**：IO 操作封装为服务类，业务逻辑与基础设施解耦
3. **模块边界清晰**：每个模块有明确的职责和导出接口

### 层次结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Novel Material V2                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                                                            │
│  │ CLI 入口    │  nm pipeline / nm search / nm tags / nm material           │
│  │ (cli/)      │                                                            │
│  └─────────────┘                                                            │
│         │                                                                    │
│         ↓                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │ Pipeline    │    │ Search      │    │ Tags        │                      │
│  │ (pipeline/) │    │ (search/)   │    │ (tags/)     │                      │
│  └─────────────┘    └─────────────┘    └─────────────┘                      │
│         │                   │                   │                            │
│         ↓                   ↓                   ↓                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │ Validation  │    │ Material    │    │ Storage     │                      │
│  │ (validation/)│   │ (material/) │    │ (storage/)  │                      │
│  └─────────────┘    └─────────────┘    └─────────────┘                      │
│         │                   │                   │                            │
│         └───────────────────┴───────────────────┘                            │
│                             │                                                │
│                             ↓                                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          契约层 (Contract Layer)                        │  │
│  │  ┌─────────────┐  ┌─────────────┐                                      │  │
│  │  │ Prompts     │  │ Schema      │  字段阈值 + 提示词模板                │  │
│  │  │ (prompts/)  │  │ (schema/)   │  YAML 契约文件为单一数据源            │  │
│  │  └─────────────┘  └─────────────┘                                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                             │                                                │
│                             ↓                                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          服务层 (Service Layer)                         │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐          │  │
│  │  │ PathService│ │YAMLService │ │ProgressMngr│ │Context     │          │  │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                             │                                                │
│                             ↓                                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          基础设施层 (Infra Layer)                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                    │  │
│  │  │ LLM         │  │ Embedding   │  │ Config      │                    │  │
│  │  │ (llm.py)    │  │ (embedding) │  │ (config.py) │                    │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                             │                                                │
│                             ↓                                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │      PostgreSQL + pgvector                                              │  │
│  │  novels / chapters / tags / characters / worldbuilding / outline       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
novel-material/
├── src/novel_material/           # 核心代码
│   ├── cli/                      # CLI 入口
│   │   ├── main.py               # 主入口：注册所有子命令
│   │   ├── pipeline.py           # 流水线命令
│   │   ├── search.py             # 检索命令
│   │   ├── tags.py               # 标签管理
│   │   ├── material.py           # 素材管理
│   │   ├── storage.py            # 数据库管理
│   │   └── validate.py           # 校验命令
│   │
│   ├── prompts/                  # [契约层] 提示词模板
│   │   ├── __init__.py           # 导出 Prompt, load_prompt
│   │   ├── prompt_loader.py      # Prompt 类 + 模板变量替换
│   │   ├── analyze.yaml          # 章级分析提示词
│   │   ├── characters.yaml       # 人物提取提示词（含子提示词）
│   │   ├── evaluate.yaml         # 总体评估提示词
│   │   ├── outline.yaml          # 大纲生成提示词
│   │   └── worldbuilding.yaml    # 世界观提取提示词
│   │
│   ├── schema/                   # [契约层] 字段契约
│   │   ├── __init__.py           # 导出 FieldSchema, load_field, get_threshold
│   │   ├── fields_loader.py      # FieldSchema 类
│   │   ├── fields.yaml           # 所有字段定义 + 阈值（单一数据源）
│   │   └── thresholds.py         # 非字段阈值获取
│   │
│   ├── analysis_profiles/        # [契约层] 题材感知深度分析 profile
│   │   ├── loader.py             # profile 加载与合并
│   │   └── profiles/*.yaml       # common/xuanhuan/xianxia/suspense
│   │
│   ├── infra/                    # 基础设施 + 服务层
│   │   ├── __init__.py           # 统一导出
│   │   ├── config.py             # 路径常量 + meta 状态更新
│   │   ├── config_service.py     # 配置加载服务
│   │   ├── llm.py                # LLM 调用客户端（多服务商 + 重试）
│   │   ├── llm_args.py           # LLM 参数构建
│   │   ├── embedding.py          # Embedding API
│   │   ├── common.py             # 公共常量 + 公共函数
│   │   ├── yaml_io.py            # [服务层] YAML IO
│   │   ├── path_service.py       # [服务层] 路径服务
│   │   ├── progress_manager.py   # [服务层] 进度管理
│   │   ├── progress.py           # 进度追踪 + PipelineRunner
│   │   ├── logging_service.py    # [服务层] 日志创建
│   │   ├── logging_config.py     # 日志配置
│   │   └── context.py            # [服务层] 执行上下文
│   │
│   ├── pipeline/                 # 流水线逻辑
│   │   ├── ingest.py             # 入库：预处理 + 章节切分
│   │   ├── preprocess.py         # 文本清洗
│   │   ├── loader.py             # 章节加载 + 摘要池构建
│   │   ├── loader_args.py        # loader 参数构建
│   │   ├── evaluate.py           # 总体评估
│   │   ├── analyze.py            # 章级分析主入口
│   │   ├── analyze_batch.py      # 批量分析逻辑
│   │   ├── analyze_single.py     # 单章分析逻辑
│   │   ├── analyze_utils.py      # 分析公共函数
│   │   ├── analyze_context.py    # 分析上下文构建
│   │   ├── analyze_files.py      # 分析文件处理
│   │   ├── analyze_temperature.py # 动态温度调节
│   │   ├── analyze_validators.py # 分析结果校验
│   │   ├── infer.py              # 结构角色推断
│   │   ├── outline_core.py       # 大纲生成核心逻辑
│   │   ├── outline_io.py         # 大纲 IO 处理
│   │   ├── outline_logic.py      # 大纲业务逻辑
│   │   ├── outline_temp.py       # 大纲模板生成
│   │   ├── worldbuilding.py      # 世界观提取
│   │   ├── characters.py         # 人物提取入口
│   │   ├── characters_core.py    # 人物提取核心
│   │   ├── characters_profile.py # 人物档案生成
│   │   ├── characters_stats.py   # 人物统计
│   │   ├── characters_layer.py   # 人物分层逻辑
│   │   ├── characters_selector.py # 人物选择器
│   │   ├── tags.py               # 标签生成
│   │   ├── insights.py           # 题材感知深度分析
│   │   ├── insights_prompt.py    # 深度分析 prompt 构造
│   │   ├── profile_resolver.py   # profile 路由
│   │   ├── runtime_modes.py      # fast/standard/deep 运行模式
│   │   ├── refine.py             # 统计精调
│   │   └── progress.py           # 进度追踪
│   │
│   ├── search/                   # 检索逻辑
│   │   ├── chapter.py            # 章节检索（向量）
│   │   ├── outline.py            # 大纲检索
│   │   ├── character.py          # 人物检索
│   │   ├── world.py              # 世界观检索
│   │   ├── event.py              # 事件检索
│   │   ├── insight.py            # chapter_insights YAML 检索
│   │   ├── detail.py             # 细节检索（内部）
│   │   └── common.py             # 共享工具
│   │
│   ├── storage/                  # 数据库层
│   │   ├── init_db.py            # 表结构初始化
│   │   ├── init_data.py          # 基础数据初始化
│   │   ├── init_tags.py          # 标签字典导入
│   │   ├── sync.py               # 同步入口（自动修复）
│   │   ├── sync_core.py          # 同步核心逻辑
│   │   ├── sync_chapters.py      # 章节同步
│   │   ├── sync_characters.py    # 人物同步
│   │   ├── sync_meta.py          # 元信息同步
│   │   ├── sync_outline.py       # 大纲同步
│   │   ├── sync_worldbuilding.py # 世界观同步
│   │   ├── sync_utils.py         # 同步工具函数
│   │   ├── repair.py             # 章节修复入口（委托 pipeline）
│   │   ├── embedding.py          # 向量化存储
│   │   ├── schema.sql            # DDL 定义
│   │   └── migrations/           # 数据库迁移脚本
│   │       ├── 001_add_key_event.sql
│   │       ├── 002_add_chapter_tags.sql
│   │       └── README.md
│   │
│   ├── tags/                     # 标签系统
│   │   ├── load.py               # 动态加载
│   │   ├── validate.py           # 校验 + 同义词
│   │   ├── resolve.py            # 领域定位
│   │   ├── export_view.py        # YAML 导出
│   │   └── scheduled.py          # 批处理审核
│   │
│   ├── validation/               # 校验层
│   │   ├── __init__.py           # 统一导出
│   │   ├── schema.py             # Schema 校验入口
│   │   ├── models.py             # Pydantic 数据模型
│   │   ├── validators.py         # 校验逻辑
│   │   ├── quality.py            # 质量校验
│   │   ├── insights.py           # chapter_insights 校验
│   │   └── pacing_normalize.py   # 节奏标准化
│   │
│   └── material/                 # 素材管理
│       ├── import_material.py    # 导入外部素材
│       ├── delete.py             # 删除素材
│       ├── classify.py           # 素材分类核心（genre+elements+style+quality）
│       └── classify_prompt.py    # 分类提示词模板
│
├── data/                         # 数据目录
│   ├── novels/                   # 素材存储
│   │   └── {material_id}/chapter_insights/ # L2 深度分析，不替代 chapters.yaml
│   ├── schemas/                  # YAML Schema 定义
│   └── tag-system/               # 标签分类学
│
├── config/                       # 配置目录
│   ├── settings.yaml             # 主配置
│   └── providers.yaml            # 多服务商配置
│
├── docs/                         # 文档
├── tests/                        # 测试
├── .claude/skills/               # Agent Skills
└── pyproject.toml                # Python 包配置
```

---

## 契约层详解

### 设计原则

契约层实现了**单一数据源**（Single Source of Truth）：

```
fields.yaml（单一数据源）
    │
    ├──→ prompts/*.yaml（提示词引用 {{summary_min}}）
    │
    ├──→ validation/models.py（Pydantic 模型读取阈值）
    │
    └──→ validation/quality.py（质量校验读取阈值）
```

**一处修改，多处生效**：修改 `fields.yaml` 中 `summary.min_length: 50` → 自动同步到提示词、schema 校验、质量校验。

### Prompts 模块

```python
from novel_material.prompts import load_prompt

# 加载提示词模板
prompt = load_prompt("analyze")
print(prompt.system_prompt)      # 已完成模板变量替换

# 提示词可引用字段阈值
# analyze.yaml 中写：{{summary_min}}
# 实际替换为：50（从 fields.yaml 读取）
```

**支持子提示词**（如 characters.yaml）：

```python
prompt = load_prompt("characters")
core_prompt = prompt.get_sub_prompt("core_prompt")
supporting_prompt = prompt.get_sub_prompt("supporting_prompt")
minor_prompt = prompt.get_sub_prompt("minor_prompt")
```

### Schema 模块

```python
from novel_material.schema import load_field, get_threshold

# 加载字段契约
field = load_field("summary")
print(field.min_length)          # 50
print(field.max_length)          # 500
print(field.validate_in)         # ["prompt", "schema", "quality"]

# 获取非字段阈值
threshold = get_threshold("character_thresholds")
print(threshold["core"])         # 50
```

**字段定义示例**（fields.yaml）：

```yaml
summary:
  description: 章节摘要
  min_length: 50
  max_length: 500
  validate_in: ["prompt", "schema", "quality"]
  # 为什么是这个值：摘要需要足够长度描述章节核心内容

character_thresholds:
  description: 人物分层出场章数阈值
  core: 50
  supporting: 10
  minor: 5
```

---

## 服务层详解

服务层封装 IO 操作，使业务逻辑与基础设施解耦。

| 服务 | 职责 | 示例用法 |
|------|------|---------|
| `yaml_io` | YAML 读写 | `load_yaml(path)`, `save_yaml(path, data)` |
| `PathService` | 路径构建 | `PathService(novel_dir).meta_path` |
| `ProgressManager` | 进度管理 | `ProgressManager.load_progress()` |
| `ExecutionContext` | 执行上下文 | `context.material_id`, `context.logger` |
| `logging_service` | 日志创建 | `create_logger(material_id, module_name)` |

**使用示例**：

```python
from novel_material.infra import PathService, load_yaml, save_yaml

# 路径服务
paths = PathService("data/novels/nm_novel_xxx")
meta = load_yaml(paths.meta_path)
meta["status"] = "analyzed"
save_yaml(paths.meta_path, meta)
```

---

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

### 总体评估阶段（LLM 调用）

```
章节索引 → 采样章节 → 5批次LLM评估 → evaluation.yaml
    │          │           │              │
章节总数    分层采样     类型/主线      全局上下文
    │       (15/50章)    阶段概要       (滑动窗口输入)
    │                        │
    └────────────────────────┴──→ 滑动窗口模式（--window）
```

### 分析阶段（LLM 调用）

```
章级分析 → 向量化 → 骨架分析 → 精调 → 同步数据库
    │         │         │        │         │
    │      embedding  outline   统计     PostgreSQL
    │      (OpenAI)   world     出场次数  novels
    │                 characters 钩子数   chapters
    │                 tags      结构推断  characters
    │                 (infer)            worldbuilding
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

---

## 核心模块详解

### CLI 层 (`cli/`)

| 命令 | 功能 | 底层调用 |
|------|------|---------|
| `nm pipeline ingest` | 入库 | `pipeline/ingest.py` |
| `nm pipeline evaluate` | 总体评估 | `pipeline/evaluate.py` |
| `nm pipeline analyze` | 章级分析 | `pipeline/analyze.py` |
| `nm pipeline outline` | 大纲生成 | `pipeline/outline_core.py` |
| `nm pipeline worldbuilding` | 世界观提取 | `pipeline/worldbuilding.py` |
| `nm pipeline characters` | 人物提取 | `pipeline/characters.py` |
| `nm pipeline tags` | 标签生成 | `pipeline/tags.py` |
| `nm pipeline insights` | 题材感知深度分析 | `pipeline/insights.py` |
| `nm pipeline refine` | 调同步 | `pipeline/refine.py` + `pipeline/infer.py` |
| `nm search chapter` | 章节检索 | `search/chapter.py` |
| `nm search insight` | 深度分析 YAML 检索 | `search/insight.py` |
| `nm storage sync` | 数据库同步（自动修复） | `storage/sync.py` → `storage/repair.py` |
| `nm material classify` | 素材分类 | `material/classify.py` |
| `nm validate schema` | Schema 校验 | `validation/schema.py` |
| `nm validate insights` | 深度分析校验 | `validation/insights.py` |

### Pipeline 层 (`pipeline/`)

**模块拆分**（analyze 为例）：

| 子模块 | 职责 |
|--------|------|
| `analyze.py` | 主入口，流程编排 |
| `analyze_batch.py` | 批量分析逻辑 |
| `analyze_single.py` | 单章分析逻辑 |
| `analyze_utils.py` | 公共函数 |
| `analyze_context.py` | 上下文构建 |
| `analyze_files.py` | 文件处理 |
| `analyze_temperature.py` | 动态温度调节 |
| `analyze_validators.py` | 结果校验 |

**容错策略**：

| 模块 | 容错 |
|------|------|
| `ingest.py` | 失败返回 None |
| `evaluate.py` | 断点续传 + 5批次采样 |
| `analyze.py` | 断点续传 + 跳过失败章节 |
| `outline_core.py` | 3层容错 + 简单划分兜底 |
| `worldbuilding.py` | 空结构兜底 |
| `characters_core.py` | 空列表兜底 |
| `tags.py` | 默认标签兜底 |
| `insights.py` | 批量生成 + 批次失败落盘占位 + 最多一次修复 |

### Validation 层 (`validation/`)

**模块拆分**：

| 子模块 | 职责 |
|--------|------|
| `schema.py` | 校验入口，调用 validators |
| `models.py` | Pydantic 数据模型定义 |
| `validators.py` | 校验逻辑实现 |
| `quality.py` | 内容质量校验 |

**校验阈值来源**：

```python
# models.py 中读取契约
from novel_material.schema import load_field

class ChapterModel(BaseModel):
    summary: str = Field(min_length=load_field("summary").min_length)
```

### Material 层 (`material/`)

**模块拆分**：

| 子模块 | 职责 |
|--------|------|
| `import_material.py` | 导入外部素材目录 |
| `delete.py` | 删除素材及关联资源 |
| `classify.py` | 素材分类核心（genre + elements + style + quality） |
| `classify_prompt.py` | 分类提示词模板构建 |

**分类功能**：

`classify.py` 实现素材分类流水线：
- 分布式采样（开头 + 中间 + 后期章节）
- LLM 推断 genre_primary / genre_secondary
- 提取 elements（设定元素）、style（叙事风格）、quality（质量评估）
- 断点续传 + 进度追踪

### Storage 层 (`storage/`)

**模块拆分**：

| 子模块 | 职责 |
|--------|------|
| `sync.py` | 同步入口，协调各 sync 模块 |
| `sync_core.py` | 同步核心逻辑 + 自动修复检测 |
| `sync_chapters.py` | 章节同步 + 检测短摘要 |
| `sync_characters.py` | 人物同步 |
| `sync_meta.py` | 元信息同步 |
| `sync_outline.py` | 大纲同步 |
| `sync_worldbuilding.py` | 世界观同步 |
| `repair.py` | 章节修复入口（委托 pipeline.analyze） |
| `init_db.py` | 表结构初始化 |
| `init_data.py` | 基础数据初始化（genre_domain_map） |
| `init_tags.py` | 标签字典导入 |

**自动修复机制**：

`sync.py` 检测到质量问题（如 summary 长度不足）时：
1. 调用 `repair.py` → 委托 `pipeline.analyze.reanalyze_chapters`
2. 重分析问题章节
3. 修复成功 → 继续同步
4. 修复失败 → 记录日志，需人工干预

### Infra 层 (`infra/`)

**导出分类**：

```python
# config - 路径常量
PROJECT_ROOT, DATA_DIR, NOVELS_DIR, CONFIG_DIR, SCHEMAS_DIR

# llm - LLM 调用
load_config, call_llm, truncate_to_tokens, get_api_stats

# embedding - 向量计算
get_embedding, get_embeddings_batch

# progress - 进度追踪
get_pipeline_logger, StageTracker, PipelineRunner

# common - 常量 + 公共函数
KEY_PLOT_POINT_VALUES, NOVEL_TYPE_VALUES
is_special_chapter_type, filter_normal_chapters

# 服务层
load_yaml, save_yaml, PathService, ProgressManager, ExecutionContext
```

---

## 数据库表结构

### 核心表

```sql
-- 小说元信息
novels (
  material_id TEXT PRIMARY KEY,
  name TEXT,
  genre TEXT[],
  word_count INTEGER,
  chapter_count INTEGER,
  status TEXT,
  premise TEXT,
  theme TEXT[],
  tags JSONB,
  created_at TIMESTAMP
)

-- 章节分析
chapters (
  material_id TEXT,
  chapter INTEGER,
  title TEXT,
  chapter_type TEXT,
  summary TEXT,
  tension_level INTEGER,
  key_event TEXT,
  key_plot_point TEXT,
  emotional_tone TEXT[],
  hook_type TEXT,
  summary_embedding vector(4096),
  PRIMARY KEY (material_id, chapter)
)

-- 人物
characters (
  material_id TEXT,
  name TEXT,
  role TEXT,
  archetype TEXT,
  arc_summary TEXT,
  appearance_count INTEGER,
  PRIMARY KEY (material_id, name)
)

-- 世界观
worldbuilding_entities (
  material_id TEXT,
  entity_type TEXT,
  name TEXT,
  description TEXT,
  PRIMARY KEY (material_id, entity_type, name)
)

-- 标签字典
tags (
  dimension VARCHAR(50),
  tag VARCHAR(100),
  domain VARCHAR(50),
  is_common BOOLEAN,
  PRIMARY KEY (dimension, tag)
)
```

---

## 容错机制

### LLM 调用容错

```
网络错误（429/5xx/超时）
├─ 指数退避重试（最多 8 次）
└─ 429 优先读取 Retry-After 响应头

参数错误（context_length_exceeded）
├─ 快速失败，不重试
└─ 立即抛出，由上层容错处理

JSON 解析失败
├─ 自动翻倍 max_tokens 重试（最多 2 次）
└─ 上限 65536 tokens

分析脚本容错
├─ outline: 3层容错 + generate_simple_acts() 兜底
├─ worldbuilding: 空结构兜底
├─ characters: 空列表兜底
├─ tags: 默认标签兜底
└─ 流程不中断，使用默认值继续
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

### 数据库同步自动修复

```
sync_novel 检测 summary 长度不足
    ↓
调用 repair.py → 委托 pipeline.analyze.reanalyze_chapters
    ↓
重分析问题章节（使用原 provider + use_window）
    ↓
修复成功 → 继续同步
修复失败 → 记录日志，需人工干预
```

手动触发修复：
```bash
nm storage sync nm_xxx --provider deepseek --window
# 自动检测并修复问题章节
```

---

## 配置系统

### 配置优先级

1. `config/providers.yaml`（多服务商配置）
2. `config/settings.yaml`（非敏感参数）
3. `.env` 环境变量（敏感信息）
4. 契约文件（`schema/fields.yaml`、`prompts/*.yaml`）

### 契约文件优先级最高

```yaml
# fields.yaml 中的阈值优先于 settings.yaml
summary:
  min_length: 50  # 此值同步到提示词、schema、quality

# 提示词可以引用契约值
# analyze.yaml:
# "摘要长度至少 {{summary_min}} 字" → 实际为 "摘要长度至少 50 字"
```

---

## 日志系统

### 日志文件

`data/novels/{material_id}/pipeline_{date}_{time}_{PID}.log`

**PID 隔离**：并发运行多个 pipeline 时日志写入不同文件。

### 日志格式

```
[material_id] 批次完成: 返回 10/10章...
[material_id 章节分析] API: 12.3s | in=4521 out=823 | finish=stop
[RATE] 重试 3/8，等待 60s: RateLimitError
```

### 错误标签

| 标签 | 含义 |
|------|------|
| `[AUTH]` | 认证错误（API Key 无效） |
| `[RATE]` | 速率限制（429） |
| `[SERVER]` | 服务端错误（5xx） |
| `[TIMEOUT]` | 超时错误 |
| `[CONN]` | 连接错误 |
| `[JSON]` | JSON 解析失败 |
