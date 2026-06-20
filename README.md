# Novel Material V2

Novel Material V2 是一个小说写作参考检索库。它将长篇小说清洗、按章切分并使用 LLM 提取章节、大纲、人物、世界观、标签和题材感知洞察，分析结果保存为 YAML，并可同步到 PostgreSQL 进行查询。

本项目负责**检索与结构化展示**；外部 Agent 和用户负责理解、比较、糅合与生成。

## 核心原则

- **YAML 是事实来源**：数据库是可以从本地产物重建的查询层。
- **契约驱动**：字段阈值集中在 `src/novel_material/schema/fields.yaml`，提示词位于 `src/novel_material/prompts/`。
- **章节是最小分析单元**：不拆分边界不稳定的场景和事件。
- **质量优先**：保留现有 4096 维向量作为质量基线，性能优化必须经过检索质量评测。
- **长流程可恢复**：流水线支持断点续传、失败记录和自动重试。

## 当前能力

| 能力 | 命令 | 主要产物 |
|---|---|---|
| 入库 | `nm pipeline ingest <file>` | `source.txt`、`chapter_index.yaml` |
| 总体评估 | `nm pipeline evaluate <id>` | `evaluation.yaml` |
| 章级分析 | `nm pipeline analyze <id>` | `chapters.yaml`、章节向量 |
| 题材感知分析 | `nm pipeline insights <id>` | `chapter_insights/*.yaml` |
| 骨架分析 | `nm pipeline outline/worldbuilding/characters/tags <id>` | 大纲、世界观、人物、标签 |
| 精调 | `nm pipeline refine <id>` | 统计与结构角色推断 |
| 断点续传 | `nm pipeline continue <id>` | 自动继续未完成阶段 |
| 素材检索 | `nm search chapter/outline/character/world/insight` | 结构化参考结果 |
| 数据同步 | `nm storage sync [id]` | PostgreSQL 查询数据 |

当前检索层仍在演进：主 CLI 的章节检索默认使用关键词匹配，已有向量分支尚未与关键词融合，也没有启用 ANN 索引。详细限制见 [系统架构](ARCHITECTURE.md)。

## 快速开始

要求 Python 3.10+、Docker，以及可用的 LLM/Embedding 配置。

```bash
pip install -e .
cp .env.example .env
make db-up
make db-init
```

入库并执行标准流水线：

```bash
nm pipeline full ./my-novel.txt --mode standard
```

查看进度和检索素材：

```bash
nm pipeline status nm_xxx
nm search chapter "开局困境" --limit 10
nm search insight "主角被压制后反杀" --limit 10
```

完整安装、配置和命令参数见 [用户手册](docs/USER_MANUAL.md)。

## 运行模式

| 模式 | 用途 | insights 行为 |
|---|---|---|
| `fast` | 优先完成基础分析和入库 | 跳过 core insights |
| `standard` | 默认无人值守流程 | 执行批量 core insights |
| `deep` | 质量优先 | core insights，并为后续关键章节深度分析保留扩展点 |

## 数据目录

```text
data/novels/nm_novel_YYYYMMDD_xxxx/
├── source.txt
├── chapter_index.yaml
├── meta.yaml
├── evaluation.yaml
├── chapters.yaml
├── chapter_embeddings.npz
├── chapter_insights/
├── outline/
├── characters/
├── worldbuilding/
└── tags.yaml
```

## 文档导航

- [项目文档索引](docs/README.md)
- [项目需求](docs/REQUIREMENTS.md)：产品边界、质量目标和规模。
- [系统架构](ARCHITECTURE.md)：当前实现、数据流和已知限制。
- [用户手册](docs/USER_MANUAL.md)：安装、命令和故障排查。
- [Agent 指南](AGENTS.md)：Codex 与通用 Agent 操作规则。
- [题材感知深度分析](docs/GENRE_AWARE_ANALYSIS.md)：insights 功能说明。

## 测试

```bash
python -m pytest -q
```
