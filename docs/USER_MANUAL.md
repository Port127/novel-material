# Novel Material V3 用户手册

本文档说明 Novel Material V3 的安装、配置、CLI 使用和故障处理。命令清单以当前 `nm --help` 输出为准。

## 1. 系统定位

Novel Material V3 是面向外部 Agent 的小说写作参考检索后端，负责清洗小说、按章切分、生成结构化分析，并提供可比较、可追溯的参考上下文。

项目不在内部生成用户最终采用的小说内容。Agent 和用户负责理解、糅合与创作。

### 1.1 数据原则

- YAML 是事实来源，PostgreSQL 是可重建查询层。
- 章节是最小分析单元，不拆分场景和事件。
- `chapters.yaml` 是稳定 L1 分析；`chapter_insights/` 是可选 L2 增强层。
- 当前 4096 维向量保留为质量基线，不因追求速度直接降维。

### 1.2 数据生命周期

```text
clean → evaluated（可选）→ analyzed → finalized
  └────────────────────────→ analyzed
严重失败 → failed
```

| 状态 | 含义 |
|---|---|
| `clean` | 已完成清洗和章节切分 |
| `evaluated` | 已生成前置导航 `evaluation.yaml`，可供分析和人物阶段只读使用 |
| `analyzed` | 已完成章级分析 |
| `finalized` | 已完成精调，可校验并同步数据库 |
| `failed` | 流水线失败，需要查看日志并继续 |

## 2. 安装与配置

### 2.1 环境要求

- Python 3.10+
- Docker Desktop 或可访问的 PostgreSQL + pgvector
- 可用的 LLM API 配置
- 可用的 Embedding 服务

### 2.2 安装

```bash
pip install -e .
nm version
nm --help
```

### 2.3 `.env`

```bash
cp .env.example .env
```

至少检查以下配置，真实密钥不得提交到 Git：

```dotenv
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=novel_material
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}

EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=qwen3-embedding
EMBEDDING_DIMENSION=4096
EMBEDDING_BASE_URL=http://localhost:11434

LLM_API_KEY_ALIYUN=your_api_key
```

当前 LLM 服务商和模型由 `config/providers.yaml` 决定；通用参数位于 `config/settings.yaml`。Embedding 配置当前由 `.env` 读取。

### 2.4 数据库

```bash
make db-up
make db-init
```

```bash
make db-up       # 启动
make db-down     # 停止
make db-shell    # 进入 psql
make db-init     # 初始化表和基础数据
```

`make db-reset` 会删除并重建数据库，只有在用户明确确认后才能执行。

## 3. CLI 总览

```text
nm
├── pipeline   数据处理流水线
├── search     素材检索
├── tags       标签管理
├── material   素材管理
├── storage    数据库和存储管理
└── validate   数据校验
```

查看真实参数：

```bash
nm <模块> --help
nm <模块> <命令> --help
```

## 4. Pipeline 流水线

当前命令：

```text
ingest analyze insights evaluate outline worldbuilding characters
tags refine full status continue report
```

### 4.1 入库与前置导航

```bash
nm pipeline ingest ./novel.txt
nm pipeline evaluate nm_xxx
```

入库生成 `source.txt`、`chapter_index.yaml` 和 `meta.yaml`，不调用 LLM。`evaluate` 生成 `evaluation.yaml`，现在定位为前置导航：它根据采样章节输出类型、前提、主线、阶段地图、核心人物候选、世界观维度、分析重点和采样覆盖范围。

`evaluation.yaml` 当前写入 schema `3.0.0`。旧版 `2.0.1` 或包含 `stage_summaries`/`core_characters_hint` 的文件会被只读适配为 v3 导航视图；读取时不会自动改写旧文件。

前置导航与 `--window` 已解耦：`--window` 只控制章级分析是否使用前章摘要；如果存在可解析的 `evaluation.yaml`，章级分析可把它作为可选导航上下文读取。`full/continue --mode standard|deep` 默认执行前置导航，`fast` 默认跳过。

### 4.2 章级分析

```bash
nm pipeline analyze nm_xxx
nm pipeline analyze nm_xxx --window
nm pipeline analyze nm_xxx --start 1 --end 100
nm pipeline analyze nm_xxx --skip-embedding
```

主要产物为 `chapters.yaml` 和 `chapter_embeddings.npz`。指定章节范围时，后续骨架分析面对的是不完整数据。`--window` 不会自动触发 `evaluate`；需要前置导航时先执行 `nm pipeline evaluate nm_xxx`，或在 `full/continue` 中使用运行模式/`--navigation` 控制。

### 4.3 题材感知深度分析

```bash
nm pipeline insights nm_xxx
nm pipeline insights nm_xxx --start 1 --end 50
nm pipeline insights nm_xxx --profile common --profile suspense
```

产物位于 `data/novels/{material_id}/chapter_insights/{chapter:04d}.yaml`。该阶段只读取已有章级分析，不替代 `chapters.yaml`，也不进入当前 PostgreSQL 同步表。

字段契约由 `common + 题材 profile` 合并生成。内置题材 profile 为 `xuanhuan`、`xianxia`、`suspense`；默认根据 `meta.yaml` 路由，`--profile` 可重复传入并显式覆盖。结果包含冲突、读者期待、写作启示、题材字段、证据、置信度和质量状态。

批次失败不会终止整本素材；输出校验失败最多自动修复一次，仍失败时在 `quality.validation_errors` 记录。检查命令：

```bash
nm validate insights nm_xxx
nm search insight "主角被压制后反杀" --mode quality --json
```

运行模式中，`fast` 跳过 insights；`standard` 默认只分析开头 100 章，可通过 `INSIGHTS_STANDARD_CHAPTER_LIMIT` 调整；`deep` 全量执行 core insights，但主流水线尚未实现独立 deep insight 生成器。

上述 `standard` 上限只作用于未显式提供范围的 `full` 和 `continue` 自动编排；传入 `--start/--end` 时用户范围覆盖默认上限。独立执行 `nm pipeline insights` 时，不指定范围仍表示全量；指定 `--start/--end` 时严格使用用户范围。`refine` 继续基于全部 L1 章级分析数据运行。

### 4.4 骨架分析与精调

```bash
nm pipeline outline nm_xxx
nm pipeline worldbuilding nm_xxx
nm pipeline characters nm_xxx
nm pipeline characters nm_xxx --repair-character 陈汉升
nm pipeline tags nm_xxx
nm pipeline refine nm_xxx
```

对应产物包括 `outline/`、`worldbuilding/`、`characters/`、`tags.yaml`，以及 refine 更新的统计和 `key_plot_point`。

人物阶段会把自适应选择的主要人物写成完整小传：`profile_level: full` 且 `biography_complete: true`，包含弧线、心理、关键场景、关系和写作借鉴边界。非目标人物写成 `profile_level: brief` 简档，保留基础描述、出场、叙事功能和关系等信息。`characters/_index.yaml` 会记录完整小传目标数、完成数、失败数和目标名单。

`--repair-character` 可重复传入，只重建指定人物 profile 并更新人物索引。该命令会修改目标人物 profile 和 `characters/_index.yaml`，真实素材上执行前应先确认 API 消耗和事实文件变更。

### 4.5 完整流水线

```bash
nm pipeline full ./novel.txt --mode standard
nm pipeline full ./novel.txt --mode fast --navigation
nm pipeline full ./novel.txt --mode standard --skip-navigation
```

常用选项：`--mode fast|standard|deep`、`--window`、`--navigation`、`--skip-navigation`、`--provider NAME`、`--start N`、`--end N`、`--skip-sync`、`--skip-embedding`。

| 模式 | 目标 | insights 行为 |
|---|---|---|
| `fast` | 优先完成基础素材 | 跳过 core insights |
| `standard` | 默认无人值守 | 默认分析开头 100 章，可通过 `INSIGHTS_STANDARD_CHAPTER_LIMIT` 调整 |
| `deep` | 质量优先 | 全量执行 core insights，并保留关键章节深度分析扩展点 |

`standard` 和 `deep` 默认执行前置导航；`fast` 默认跳过前置导航，但可通过 `--navigation` 强制执行。`--skip-navigation` 会跳过前置导航，即使处于 `standard`/`deep` 模式。`--window` 仍只影响章级分析上下文，不决定是否运行 `evaluate`。

`full` 在 refine 后执行只读产物审计，再根据严重度决定终态：`blocker` 使运行失败并阻止数据库同步，`error` 使运行降级但允许同步，`warning/info` 不单独使运行失败。每次运行会写出：

```text
data/novels/{material_id}/reports/
├── runs/{run_id}.yaml   # 不可变机器可读报告
├── latest.yaml          # 最新机器可读报告
└── latest.md            # 最新人类可读报告
```

报告包含阶段耗时与计数、API/Token/预估成本（可用时）、诊断、产物质量问题、复审预算及建议动作。

### 4.6 状态与断点续传

```bash
nm pipeline status nm_xxx
nm pipeline continue nm_xxx --mode standard
nm pipeline continue nm_xxx --mode fast --navigation
nm pipeline continue nm_xxx --mode standard --skip-navigation
```

`continue` 自动检查未完成阶段。若 navigation 启用且缺少可解析的 `evaluation.yaml`，会从 `evaluation` 阶段恢复；若使用 `fast` 或 `--skip-navigation`，缺少 evaluation 不会阻塞续传。

结构化日志完整但报告缺失时，可只读重建：

```bash
nm pipeline report nm_xxx
nm pipeline report nm_xxx --run-id run_xxx
```

不指定 `--run-id` 时使用当前素材状态中的最新运行 ID。命令成功后输出 `latest.md` 路径，不会重跑分析或修改事实产物。

### 4.7 稳定退出码

| 退出码 | 含义 |
|---:|---|
| `0` | `success`，命令成功 |
| `1` | `failed`，业务失败或 blocker |
| `2` | 参数/用法错误 |
| `3` | `degraded`，有 error 级问题或部分失败 |
| `130` | 用户中断 |

## 5. Search 检索

主 CLI 暴露 `chapter`、`event`、`outline`、`character`、`world`、`detail`、`insight` 七类检索。默认 `quality` 模式执行中文词法、4096 维精确语义和结构化三路召回，再做 RRF、多样性、可选重排和上下文补全。

### 5.1 使用示例

```bash
nm search chapter "开局困境" --mode quality --limit 10 --json
nm search event "雨中告别" --mode quality --json
nm search outline --query "废柴逆袭" --genre 玄幻 --json
nm search character --archetype 导师 --role supporting --json
nm search world "宗门" --dimension factions --json
nm search detail "高潮前铺垫" --mode quality --json
nm search insight "主角被压制后反杀" --json
```

通用参数为 `--mode quality|exact`、`--candidate-limit N`、`--time-budget N`、`--limit N` 和 `--json`。JSON 的 `trace.degraded` 与 `degradation_reasons` 说明 embedding、重排、时间预算或上下文降级。已有数据库先执行 `nm storage migrate`。

### 5.2 当前已知限制

- 4096 维向量保持精确排序，生产环境没有 ANN 索引。
- `insight` 扫描本地 YAML，不使用 PostgreSQL 向量表。
- LLM 重排接口已实现，但人工质量对比完成前默认 `identity`。
- Golden Query 人工标注和三档容量实测尚未完成，不得声称混合检索质量不低于精确基线。

## 6. Tags 标签管理

```bash
nm tags stats
nm tags list [--dimension TEXT]
nm tags add <dimension> <tag> <domain> [--group TEXT]
nm tags remove <dimension> <tag>
nm tags review [--auto]
nm tags move <dimension> <tag> <new_domain>
nm tags set-synonym <dimension> <tag> <standard_tag>
nm tags export
nm tags info <dimension> <tag>
```

## 7. Material 素材管理

```bash
nm material list
nm material import <directory>
nm material delete --id <material_id>
nm material classify status
nm material classify start [--limit N]
nm material classify retry --seq N
nm material classify retry --failed
nm material classify clean
```

删除会影响本地 YAML、数据库和索引，必须获得用户确认。分类用于正式入库前的题材、元素、风格和质量评估。

## 8. Storage 数据库管理

```bash
nm storage init-db
nm storage init-data
nm storage init-tags
nm storage sync [material_id] [--provider NAME] [--window]
```

`sync` 不传素材 ID 时同步全部素材。注意：同步预检发现短摘要、缺章或 schema 错误时，可能调用 LLM 自动修复并修改 YAML，同时产生 API 消耗。

## 9. Validate 校验

```bash
nm validate validate [material_id]
nm validate validate --all
nm validate quality <material_id> [--start N] [--end N]
nm validate insights <material_id>
nm validate artifacts <material_id> [--review]
```

- `validate`：检查 YAML 结构和完整性。
- `quality`：检查摘要长度、覆盖率等内容质量。
- `insights`：检查题材感知字段、证据和置信度。
- `artifacts`：只读检查核心文件、章节覆盖、人物兜底档案、完整小传目标、世界观和 insights 等产物质量；默认不调用 LLM。

`--review` 只复审规则标记为可疑的项目，并受配置中的调用次数和预计耗时预算约束。预算耗尽的项目保留为“因预算未复审”，不会偷偷扩大调用。该命令不会修复或改写 YAML。

## 10. 常用流程

### 10.1 标准入库

```bash
nm pipeline full ./novel.txt --mode standard
nm pipeline full ./novel.txt --mode fast --navigation
nm pipeline full ./novel.txt --mode standard --skip-navigation
```

### 10.2 分步执行

```bash
nm pipeline ingest ./novel.txt
nm pipeline analyze nm_xxx
nm pipeline outline nm_xxx
nm pipeline worldbuilding nm_xxx
nm pipeline characters nm_xxx
nm pipeline tags nm_xxx
nm pipeline insights nm_xxx
nm pipeline refine nm_xxx
nm validate validate nm_xxx
nm storage sync nm_xxx
```

### 10.3 从断点继续

```bash
nm pipeline status nm_xxx
nm pipeline continue nm_xxx --mode standard
```

## 11. 故障排查

### API Key 或服务商错误

检查 `.env` 中对应的 API Key，以及 `config/providers.yaml` 的 `default_provider`、`base_url` 和 `api_key_env`。

### 速率限制或网络错误

LLM 客户端会指数退避重试，429 会优先读取服务商等待时间。不要在重试期间重复启动同一任务。

### 上下文超限

`context_length_exceeded` 会快速失败。检查批次大小、章节长度和摘要池 token 配置，不要盲目增加重试次数。

### Pipeline 中断

```bash
nm pipeline status nm_xxx
nm pipeline continue nm_xxx
```

不要手工修改进度文件或跳过依赖阶段。

### 报告缺失或无法重建

先确认 `logs/{YYYY-MM-DD}/` 下存在对应 `run_id` 的结构化 JSONL，再执行：

```bash
nm pipeline report nm_xxx --run-id run_xxx
```

`run_events_missing` 表示没有找到该 run 的事件；`report_rebuild_failed` 表示事件不完整、历史报告损坏或不可变 run 报告发生内容冲突。不要删除已有 `reports/runs/*.yaml` 来绕过冲突，应先核对 run ID 和日志完整性。

### 审计阻止同步或运行降级

查看 `reports/latest.md` 的“问题与风险”和“下一步”。`blocker` 会阻止 sync；`error` 返回退出码 `3`，但流水线可以完成同步。可独立运行 `nm validate artifacts nm_xxx` 复查，只有需要判断模糊项时才加 `--review`。

### 数据库或同步失败

```bash
make db-up
nm storage init-db
nm storage init-data
nm validate validate nm_xxx
nm validate quality nm_xxx
nm storage sync nm_xxx
```

如果自动修复仍失败，查看 `logs/` 和素材目录中的流水线日志。

## 12. 配置与日志

| 配置 | 位置 |
|---|---|
| LLM 服务商和模型 | `config/providers.yaml` |
| 通用运行参数 | `config/settings.yaml` |
| Embedding provider/model/dimension | `.env` |
| 字段阈值 | `src/novel_material/schema/fields.yaml` |
| 提示词 | `src/novel_material/prompts/` |
| 题材 profiles | `src/novel_material/analysis_profiles/profiles/` |

结构化运行日志位于 `logs/{YYYY-MM-DD}/{command}_{run_id}.jsonl`，用于逐事件诊断和报告重建；素材目录中的兼容文本日志保留模块细节。运行报告位于 `data/novels/{material_id}/reports/`。所有结构化输出都会做敏感信息脱敏。字段阈值以契约文件为准，不要在业务代码或文档中复制维护。

## 附录：命令速查

```bash
# Pipeline
nm pipeline ingest <file>
nm pipeline analyze <id>
nm pipeline insights <id>
nm pipeline evaluate <id>
nm pipeline outline <id>
nm pipeline worldbuilding <id>
nm pipeline characters <id>
nm pipeline characters <id> --repair-character <name>
nm pipeline tags <id>
nm pipeline refine <id>
nm pipeline full <file> --mode standard
nm pipeline status <id>
nm pipeline continue <id>
nm pipeline report <id> [--run-id RUN_ID]

# Search
nm search outline --query <text>
nm search character --name <name>
nm search chapter <keyword>
nm search world <keyword>
nm search insight <keyword>

# Tags
nm tags stats
nm tags list
nm tags add <dimension> <tag> <domain>
nm tags remove <dimension> <tag>
nm tags review
nm tags move <dimension> <tag> <new_domain>
nm tags set-synonym <dimension> <tag> <standard_tag>
nm tags export
nm tags info <dimension> <tag>

# Material
nm material list
nm material import <directory>
nm material delete --id <id>
nm material classify status
nm material classify start
nm material classify retry --failed
nm material classify clean

# Storage
nm storage init-db
nm storage init-data
nm storage init-tags
nm storage sync [id]

# Validate
nm validate validate [id]
nm validate validate --all
nm validate quality <id>
nm validate insights <id>
nm validate artifacts <id> [--review]
```
