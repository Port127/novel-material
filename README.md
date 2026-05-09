# Novel Material V2

小说素材管理系统。通过 LLM 对小说进行结构化解析（大纲、世界观、人物、章级分析），存储到 YAML + PostgreSQL，提供语义检索服务。

## 核心设计理念

1. **AI 协作优先**：本项目为 AI Agent 提供检索服务，而非 Web 界面。详见 [AGENTS.md](AGENTS.md)。
2. **YAML 为 Source of Truth**：分析结果优先落盘为 YAML，数据库是可重建的查询层。
3. **章节为最小粒度**：不拆分难以定义边界的"事件"或"场景"。详见 [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)。

## 功能概览

| 功能 | 命令 | 说明 |
|------|------|------|
| 入库 | `nm pipeline ingest <file>` | 文本清洗 + 章节切分 |
| 完整流水线 | `nm pipeline full <file>` | 入库 → 分析 → 骨架 → 精调 |
| 章级分析 | `nm pipeline analyze <id>` | 摘要、张力、人物、功能（支持范围） |
| 骨架分析 | `nm pipeline outline/world/char/tags <id>` | 大纲、世界观、人物、标签 |
| 断点续传 | `nm pipeline continue <id>` | 自动从上次进度继续 |
| 精调 | `nm pipeline refine <id>` | 统计精调 + 数据库同步 |
| 检索 | `nm search <type> <query>` | 章节/人物/世界观/大纲/事件 |
| 标签管理 | `nm tags stats/list/add` | 查看/添加/审核标签 |
| 素材管理 | `nm material list/import/delete` | 查看/导入/删除素材 |
| 数据校验 | `nm validate schema/quality <id>` | 结构校验/质量校验 |

## 快速开始

完整操作指南见 [docs/USER_MANUAL.md](docs/USER_MANUAL.md)。以下为骨架流程：

### 1. 安装

```bash
pip install -e .
```

### 2. 配置

```bash
cp .env.example .env
# 必须填入 DATABASE_URL、LLM_API_KEY、EMBEDDING_API_KEY
```

### 3. 启动数据库

```bash
make db-up && make db-init
```

### 4. 入库小说

```bash
nm pipeline full ./my-novel.txt
```

### 5. 检索

```bash
nm search chapter "开局困境" --limit 10
```

## 文档导航

| 文档 | 给谁看 | 解决什么问题 |
|------|--------|-------------|
| **[REQUIREMENTS.md](docs/REQUIREMENTS.md)** | 决策者 | 做什么、不做什么、为什么 |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | 开发者 | 系统怎么构建的、数据流向 |
| **[USER_MANUAL.md](docs/USER_MANUAL.md)** | 使用者 | 怎么用、命令参考、故障排查 |
| **[AGENTS.md](AGENTS.md)** | AI Agent | 操作本项目的规则和约束 |

推荐阅读顺序：REQUIREMENTS → ARCHITECTURE → USER_MANUAL → AGENTS。

其他：
- **[data/schemas/](data/schemas/)**：YAML Schema 定义
- **[data/tag-system/](data/tag-system/)**：标签分类学体系

## 容错特性

内置断点续传、自动重试、默认值兜底。详见 [docs/USER_MANUAL.md](docs/USER_MANUAL.md) 第 16 章。

## 数据产物

完整流水线后生成：

```
data/novels/nm_novel_YYYYMMDD_xxxx/
├── source.txt           # 清洗后的原文
├── meta.yaml            # 元信息（状态、题材、字数）
├── chapter_index.yaml   # 章节索引
├── chapters.yaml        # 章级分析（摘要、张力、功能、人物）
├── chapter_embeddings.npz  # 向量缓存
├── outline/             # 大纲结构
│   ├── structure.yaml   # 三幕结构 + 序列节拍
│   ├── plotlines.yaml   # 副线追踪
│   ├── hooks_network.yaml  # 钩子网络
│   └── _index.yaml      # 大纲索引
├── characters/          # 人物档案
│   ├── profiles/*.yaml  # 人物详情
│   └── relations.yaml   # 人物关系
├── worldbuilding/       # 世界观
│   ├── factions.yaml    # 势力设定
│   ├── regions.yaml     # 地域设定
│   ├── power_systems.yaml  # 力量体系
│   └── _index.yaml      # 世界观索引
├── tags.yaml            # 小说级标签
└── pipeline.log         # 流水线日志
```

## Makefile 命令

仅用于 Docker 管理：

```bash
make db-up      # 启动数据库容器
make db-down    # 停止容器
make db-init    # 初始化表结构
make db-shell   # 进入 psql
make db-reset   # 重置数据库（危险）
```

其他操作使用 `nm` CLI。

## 多服务商支持

支持配置多个 LLM 服务商。详见 `config/providers.yaml`。使用时通过 `--provider` 参数切换。

## 测试

```bash
python -m pytest tests/
```