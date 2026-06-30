# Novel Material V3 - 系统架构

本文档描述系统的真实架构、数据流向和模块边界。

## 相关文档

- [REQUIREMENTS.md](docs/REQUIREMENTS.md) — 业务边界与不做什么（为什么这样设计）
- [USER_MANUAL.md](docs/USER_MANUAL.md) — 详细使用手册（如何使用）
- [AGENTS.md](AGENTS.md) — Agent 操作规则
- [README.md](README.md) — 项目入口与快速开始
- [文档索引](docs/README.md) — 现行文档、工作记录与阅读顺序

---

## 架构总览

### 设计理念

本项目采用**契约驱动设计**（Contract-Driven Design），核心原则：

1. **单一数据源**：所有校验阈值、提示词参数集中在 YAML 契约文件，一处修改多处生效
2. **服务层抽象**：IO 操作封装为服务类，业务逻辑与基础设施解耦
3. **模块边界清晰**：每个模块有明确的职责和导出接口
4. **运行可验证**：结构化事件统一驱动日志、终端摘要和运行报告，审计只读检查事实产物

### 层次结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Novel Material V3                                    │
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
│   │   ├── evaluate.yaml         # 前置导航提示词
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
│   ├── runtime/                  # 中立运行契约、事件分发、状态与 workspace guard
│   ├── run_logging/              # 结构化 JSONL 日志、脱敏与运行事件读取
│   ├── terminal/                 # Rich 进度展示和终态摘要（不负责报告写入）
│   ├── audit/                    # 只读产物规则、严重度映射与受限可选复审
│   ├── reporting/                # 报告聚合、Markdown 渲染、原子持久化与 ReportSink
│   ├── worldbuilding/            # 分层世界观契约、旧格式只读适配、维度路由和写入
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
│   │   ├── evaluate.py           # 前置导航评估，输出 evaluation.yaml v3
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
│   │   ├── work_profile.py       # 作品画像生成，输出 work_profile.yaml
│   │   ├── work_profile_models.py # 作品画像稳定契约
│   │   ├── work_profile_prompt.py # 作品画像提示词构造
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
│   │   ├── stages.py             # 阶段入口到 StageResult 的适配
│   │   ├── state.py              # 运行状态持久化
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
├── .agents/skills/               # Codex/通用 Agent Skills
├── .claude/skills/               # Claude Code Skills
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

### 前置导航阶段（LLM 调用）

```
章节索引 → 采样章节 → 5批次LLM评估 → evaluation.yaml
    │          │           │              │
章节总数    分层采样     类型/主线      全局导航
    │       (15/50章)    阶段地图       (可被分析/人物阶段只读使用)
    │
    └──→ full/continue 默认由 standard/deep 启用；fast 可用 --navigation 强制启用
```

`evaluate` 现在是“前置导航”阶段，不再等同于 `--window`。`--window` 只控制章级分析是否带前章摘要；若素材中存在可解析的 `evaluation.yaml`，章级分析会把前置导航作为可选上下文读取。`pipeline full/continue --mode standard|deep` 默认执行前置导航；`--skip-navigation` 可跳过；`fast` 默认跳过，但可用 `--navigation` 强制执行。

`evaluation.yaml` 当前写入 schema `3.0.0`，核心字段包括 `novel_type`、`premise`、`main_thread_summary`、`stage_map`、`core_character_candidates`、`worldbuilding_dimensions`、`analysis_focus`、`sample_coverage` 和 `evaluation_timestamp`。读取侧通过 `pipeline/evaluation_models.py` 提供只读兼容视图：旧版 `2.0.1` 或包含 `stage_summaries`/`core_characters_hint` 的文件会被适配为 v3 导航对象，但不会在读取时自动改写原文件。

### 分析阶段（LLM 调用）

```
章级分析 ─┬→ 向量化 ─────────────────┐
          ├→ insights（按运行模式）   │
          └→ 骨架分析 → 精调 → 作品画像 ┼→ 审计 → 同步数据库
                 │         │          │          │
              outline    统计      work_profile PostgreSQL
              world      出场次数              novels
              characters 钩子数                chapters
              tags       结构推断              characters
                                              worldbuilding
                                              outline_sequences
                                              outline_beats
```

`chapters.yaml` 是稳定的 L1 章级分析结果。`chapter_insights/{chapter:04d}.yaml` 是可选 L2 增强层，由 `common + 题材 profile + 可选叙事 profile` 合并字段契约后批量生成，不替代 L1，也不进入当前 PostgreSQL 同步表。

首批 profile 包括 `common`、`xuanhuan`、`xianxia`、`suspense`。`profile_resolver.py` 根据 `meta.yaml` 题材选择，也接受 CLI `--profile` 显式覆盖；`analysis_profiles/` 负责加载和合并 YAML 契约。单章 insight 包含 `profiles`、`common`、`genre`、`evidence`、`confidence` 和 `quality`，题材字段必须能关联章级摘要或已有字段证据。

`fast` 模式跳过 insights；`standard` 模式默认只为开头 100 章生成 core insights，上限由 `INSIGHTS_STANDARD_CHAPTER_LIMIT` 配置；`deep` 当前仍对全部已分析章节调用同一个 core insight 生成器。`full/continue --start/--end` 的显式用户范围覆盖模式默认范围。`deep` 的关键章节比例与阻断语义只是扩展元数据，尚无独立 deep 分析实现，文档和 Agent 不得声称已经完成更深层分析。该自动上限不影响独立 `nm pipeline insights --start/--end`，也不缩小 `refine` 的全书 L1 输入范围。

`insights.py` 按批调用 LLM，批次失败会为对应章节写入失败状态并继续；schema 校验失败最多修复一次，仍失败则保留结果并写入 `quality.validation_errors`，同时下调 confidence。新增 profile 时必须提供 YAML 字段契约，并覆盖 loader、resolver、prompt 和 validator 测试。

### 人物档案与完整小传

`characters` 阶段先从章级出场统计和前置导航候选构造人物信号，再自适应选择 5–12 名主要人物生成完整小传。完整小传 profile 使用 `profile_level: full` 与 `biography_complete: true`，包含人物弧线、心理动机、关系、关键场景和写作借鉴边界；其他达到候选阈值的人物写为 `profile_level: brief` 简档，只保留基础描述、叙事功能、出场和关系等可用信息。

人物索引 `characters/_index.yaml` 记录 `biography_target_count`、`biography_completed_count`、`biography_failed_count`、`biography_selection_reason` 和 `biography_targets`。产物审计会把完整小传目标缺失、伪完成或主要人物空壳标为 error，并在运行报告中展示完整小传目标/完成/失败/简档数量。

定向修复命令为：

```bash
nm pipeline characters nm_xxx --repair-character 陈汉升
```

该命令只删除并重建指定人物的 profile，同时更新人物索引；它会修改素材事实文件，真实素材上执行前必须获得用户明确授权。默认只读验收只运行 `nm validate artifacts`，不会触发 LLM 修复。

### 分层世界观与作品画像

`worldbuilding` 阶段当前写入分层布局。`worldbuilding/_index.yaml` 记录 schema、layout、实体/关系/证据计数和旧格式兼容状态；`overview.yaml` 保存世界观概览和运行机制；`dimensions.yaml` 用 `applicable`、`not_applicable`、`uncertain` 结构化表达题材维度是否适用；`entities/*.yaml` 保存稳定实体 ID、类型、名称、描述、重要性、首次出现、关键出场、证据和置信度；`relations.yaml` 保存实体关系、演化、证据和置信度。

旧素材的四类世界观文件仍通过 `worldbuilding.reader.load_worldbuilding_view()` 只读适配为统一视图，读取时不会自动改写旧 YAML。`embedding`、`storage sync`、`search world` 和审计都通过统一读取器消费世界观实体，避免各层重复理解新旧布局。同步层会把 layered 实体写入 `worldbuilding_entities.properties`，包括 `entity_id`、`dimension_ids`、证据、关键出场和关系摘要；搜索结果会返回这些 metadata，并保留 `organization`/`factions`、`location`/`region`/`regions` 等旧过滤别名兼容。

`profile` 阶段生成素材根目录下的 `work_profile.yaml`。它是面向写作 Agent 的作品级入口，汇总作品钩子、读者期待、结构节奏、人物动力、世界观驱动、技法启示、证据索引和限制；它只引用 `chapters.yaml`、`characters/`、`worldbuilding/` 等下层事实产物，不替代事实文件，也不是搜索质量评测结论。`nm pipeline profile nm_xxx` 可独立执行；`full`、`continue` 和 `status` 已识别该阶段。

真实素材上的 `worldbuilding`、`characters --repair-character`、`profile`、`full` 或 `continue` 都可能调用 LLM 并修改事实文件；执行前必须获得用户明确授权。默认验收只运行只读校验和报告生成，不触发真实素材 LLM 重跑。

### 运行审计与报告

`full` 和 `continue` 通过中立 `RunEvent` 串联运行观察能力，业务阶段不直接依赖终端或报告写入器：

```text
Pipeline / LLM ──→ RunEvent ──→ RuntimeDispatcher
                                  ├─ JsonlSink（required）→ logs/YYYY-MM-DD/*.jsonl
                                  ├─ ReportSink（required）→ reports/runs/{run_id}.yaml
                                  │                         ├→ reports/latest.yaml
                                  │                         └→ reports/latest.md
                                  └─ TerminalSink（best effort）→ 进度与终态摘要

refine → artifact audit ─┬─ blocker → failed，不执行 sync
                         ├─ error   → degraded，可继续 sync
                         └─ warning/info → success，可继续 sync
```

`audit/` 只读取素材目录内的事实文件，检查核心产物存在性、章节覆盖、人物兜底档案、世界观与 insights 等质量信号。默认执行确定性规则；只有显式 `--review` 才启用带时间和调用次数上限的 LLM 复审。审计与报告不得修改事实文件，允许新增内容仅位于 `reports/`。

`reporting/` 从事件构建统一报告，包含运行状态、阶段耗时与计数、API/Token/成本（可用时）、诊断、产物问题、复审预算和下一步动作。每个 run YAML 是不可变记录；`latest.yaml` 与 `latest.md` 使用原子替换。`ReportSink` 是流水线 required sink，写入失败会使运行失败；终端展示仍是 best effort。

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
| `nm pipeline evaluate` | 前置导航评估 | `pipeline/evaluate.py` |
| `nm pipeline analyze` | 章级分析 | `pipeline/analyze.py` |
| `nm pipeline outline` | 大纲生成 | `pipeline/outline_core.py` |
| `nm pipeline worldbuilding` | 世界观提取 | `pipeline/worldbuilding.py` |
| `nm pipeline characters` | 人物提取 | `pipeline/characters.py` |
| `nm pipeline tags` | 标签生成 | `pipeline/tags.py` |
| `nm pipeline insights` | 题材感知深度分析 | `pipeline/insights.py` |
| `nm pipeline refine` | 精调 | `pipeline/refine.py` + `pipeline/infer.py` |
| `nm pipeline profile` | 作品画像生成 | `pipeline/work_profile.py` |
| `nm pipeline report` | 从结构化日志只读重建报告 | `reporting/` + `run_logging/reader.py` |
| `nm search chapter` | 章节检索 | `search/chapter.py` |
| `nm search insight` | 深度分析 YAML 检索 | `search/insight.py` |
| `nm storage sync` | 数据库同步（自动修复） | `storage/sync.py` → `storage/repair.py` |
| `nm material classify` | 素材分类 | `material/classify.py` |
| `nm validate validate` | Schema 完整性校验 | `validation/schema.py` |
| `nm validate insights` | 深度分析校验 | `validation/insights.py` |
| `nm validate artifacts` | 只读产物质量审计，可选受限复审 | `audit/` |

### Runtime、Audit 与 Reporting

| 模块 | 职责 | 依赖边界 |
|---|---|---|
| `runtime/` | 统一状态、退出码、事件、dispatcher、汇总和工作区保护 | 中立共享依赖，不依赖 UI |
| `run_logging/` | JSONL 持久化、敏感信息脱敏、按 run 读取事件 | 不依赖 `terminal/` |
| `terminal/` | 消费事件并展示进度、问题摘要和报告路径 | 可读 `reporting.models`，不得依赖 `reporting.writer` |
| `audit/` | 只读规则、问题模型、预算化复审 | 不依赖 storage、terminal、report writer |
| `reporting/` | 事件聚合、报告模型、Markdown 与持久化 | 不依赖 storage、业务 pipeline、terminal |

这些边界由 AST 测试锁定；端到端只读测试还会对审计前后的事实文件逐一计算 SHA-256，确保审计、复审和报告生成只在 `reports/` 下新增文件。

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
| `evaluate.py` | 前置导航评估，断点续传 + 5批次采样 |
| `analyze.py` | 断点续传 + 跳过失败章节 |
| `outline_core.py` | 3层容错 + 简单划分兜底 |
| `worldbuilding.py` | 空结构兜底 |
| `characters_core.py` | 空列表兜底 |
| `tags.py` | 默认标签兜底 |
| `insights.py` | 批量生成 + 批次失败落盘占位 + 最多一次修复 |

### Search 层 (`search/`)

`SearchService` 是外部 Agent 的上下文供应层。`quality` 模式编排中文词法、完整 4096 维语义和结构化过滤三路召回，经 RRF、跨素材多样性和可插拔重排后，批量补充邻章摘要与原文行号。单路失败写入 trace 并降级，全部通道失败才报错。

`exact` 模式只执行 4096 维语义精确排序。生产 schema 不启用 ANN；候选实验必须通过 `docs/search-benchmark.md` 的质量门禁。七类公开命令统一返回 `SearchResponse`。LLM 重排默认关闭；人工 Golden Query 基线补齐前，不得宣称混合或重排质量优于精确基线。

分层世界观、实体关系、`work_profile.yaml` 作品画像、存储适配和 `search world` metadata 适配已经接入当前实现。它们让新旧世界观结构可统一读取、同步和检索，并为写作 Agent 提供更完整的作品级入口；但人工 Golden Query 基线尚未补齐，文档、报告和 Agent 仍不得据此声称人物检索、世界观检索或整体检索质量已经提升。

### Validation 层 (`validation/`)

**模块拆分**：

| 子模块 | 职责 |
|--------|------|
| `schema.py` | 校验入口，调用 validators |
| `models.py` | Pydantic 数据模型定义 |
| `validators.py` | 校验逻辑实现 |
| `quality.py` | 内容质量校验 |
| `insights.py` | chapter_insights 契约与质量校验 |

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
  type TEXT,
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
  arc_summary_embedding vector(4096),
  appearance_count INTEGER,
  PRIMARY KEY (material_id, name)
)

-- 世界观
worldbuilding_entities (
  material_id TEXT,
  entity_type TEXT,
  name TEXT,
  description TEXT,
  description_embedding vector(4096),
  properties JSONB,
  first_appearance TEXT,
  importance TEXT,
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

结构化运行日志位于 `logs/{YYYY-MM-DD}/{command}_{run_id}.jsonl`；达到配置的大小上限后以数字后缀轮转。每行是一个已脱敏的 `RunEvent`，可供 `nm pipeline report` 重建报告。

素材目录仍可保留阶段级兼容日志，例如 `data/novels/{material_id}/pipeline_{date}_{time}_{PID}.log`，用于查看旧模块的详细文本信息。

**运行隔离**：结构化日志以 `run_id` 隔离，兼容文本日志以 PID 隔离。

### 日志格式

```
[RunStarted / StageCompleted / ArtifactAuditCompleted / RunCompleted JSONL]
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
