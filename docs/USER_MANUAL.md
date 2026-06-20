# Novel Material V2 用户手册

本文档说明 Novel Material V2 的安装、配置、CLI 使用和故障处理。命令清单以当前 `nm --help` 输出为准。

## 1. 系统定位

Novel Material V2 是小说写作参考检索库，负责清洗小说、按章切分、生成结构化分析，并向外部 Agent 提供可比较、可追溯的写作参考。

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
| `evaluated` | 已生成总体评估，用于滑动窗口上下文 |
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
tags refine full status continue
```

### 4.1 入库与总体评估

```bash
nm pipeline ingest ./novel.txt
nm pipeline evaluate nm_xxx
```

入库生成 `source.txt`、`chapter_index.yaml` 和 `meta.yaml`，不调用 LLM。总体评估是可选步骤，主要为滑动窗口提供全局上下文。

### 4.2 章级分析

```bash
nm pipeline analyze nm_xxx
nm pipeline analyze nm_xxx --window
nm pipeline analyze nm_xxx --start 1 --end 100
nm pipeline analyze nm_xxx --skip-embedding
```

主要产物为 `chapters.yaml` 和 `chapter_embeddings.npz`。指定章节范围时，后续骨架分析面对的是不完整数据。

### 4.3 题材感知深度分析

```bash
nm pipeline insights nm_xxx
nm pipeline insights nm_xxx --start 1 --end 50
nm pipeline insights nm_xxx --profile common --profile suspense
```

产物位于 `data/novels/{material_id}/chapter_insights/{chapter:04d}.yaml`。该阶段只读取已有章级分析，不替代 `chapters.yaml`。详情见 [题材感知深度分析](GENRE_AWARE_ANALYSIS.md)。

### 4.4 骨架分析与精调

```bash
nm pipeline outline nm_xxx
nm pipeline worldbuilding nm_xxx
nm pipeline characters nm_xxx
nm pipeline tags nm_xxx
nm pipeline refine nm_xxx
```

对应产物包括 `outline/`、`worldbuilding/`、`characters/`、`tags.yaml`，以及 refine 更新的统计和 `key_plot_point`。

### 4.5 完整流水线

```bash
nm pipeline full ./novel.txt --mode standard
```

常用选项：`--mode fast|standard|deep`、`--window`、`--provider NAME`、`--start N`、`--end N`、`--skip-sync`、`--skip-embedding`。

| 模式 | 目标 | insights 行为 |
|---|---|---|
| `fast` | 优先完成基础素材 | 跳过 core insights |
| `standard` | 默认无人值守 | 执行批量 core insights |
| `deep` | 质量优先 | 执行 core insights，并保留关键章节深度分析扩展点 |

### 4.6 状态与断点续传

```bash
nm pipeline status nm_xxx
nm pipeline continue nm_xxx --mode standard
```

`continue` 自动检查未完成阶段。滑动窗口模式需要已有 `evaluation.yaml`。

## 5. Search 检索

当前主 CLI 暴露五类检索：`outline`、`character`、`chapter`、`world`、`insight`。

### 5.1 使用示例

```bash
nm search chapter "开局困境" --limit 10
nm search outline --query "废柴逆袭" --genre 玄幻 --limit 10
nm search character --name 杨间
nm search character --archetype 导师 --role supporting --limit 10
nm search world "宗门" --dimension factions --limit 10
nm search world "境界" --dimension power_systems
nm search insight "主角被压制后反杀" --limit 10
```

Insight 搜索顺序扫描本地 `chapter_insights/*.yaml` 的冲突、读者期待、写作启示和题材字段，不使用 PostgreSQL 或向量搜索。

### 5.2 当前已知限制

- 章节主 CLI 默认走关键词 `ILIKE`，没有暴露底层 `semantic` 参数。
- 关键词与向量查询是独立分支，不是混合召回。
- PostgreSQL 向量列为 4096 维，当前没有启用 ANN 索引。
- 关键词查询尚未实现中文全文索引和统一相关度排名。
- `src/novel_material/search/event.py` 与 `detail.py` 是内部模块，没有注册到 `nm search`。
- 章节、大纲、人物和世界观底层搜索函数仍混合查询和打印职责，主 CLI 可能重复提示未找到。
- 项目尚未建立完整检索基准集，不应仅凭相似度数字判断质量。

后续检索改造以质量为第一目标，允许深度检索最长约三分钟；任何降维或近似索引都必须先与 4096 维精确检索比较。

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
```

- `validate`：检查 YAML 结构和完整性。
- `quality`：检查摘要长度、覆盖率等内容质量。
- `insights`：检查题材感知字段、证据和置信度。

## 10. 常用流程

### 10.1 标准入库

```bash
nm pipeline full ./novel.txt --mode standard
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

日志位于 `logs/`，按 pipeline、search、embedding 等模块分开记录。字段阈值以契约文件为准，不要在业务代码或文档中复制维护。

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
nm pipeline tags <id>
nm pipeline refine <id>
nm pipeline full <file> --mode standard
nm pipeline status <id>
nm pipeline continue <id>

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
```
