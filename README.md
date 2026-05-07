# Novel Material V2

小说素材管理系统。通过 LLM 对小说进行结构化解析（大纲、世界观、人物、章级分析），存储到 YAML + PostgreSQL，提供语义检索服务。

## 核心设计理念

1. **AI 协作优先**：本项目为 AI Agent 提供检索服务，而非 Web 界面。详见 [AGENTS.md](AGENTS.md)。
2. **YAML 为 Source of Truth**：分析结果优先落盘为 YAML，数据库是可重建的查询层。
3. **章节为最小粒度**：不拆分难以定义边界的"事件"或"场景"。详见 [REQUIREMENTS.md](docs/REQUIREMENTS.md)。

## 功能概览

| 功能 | 命令 | 说明 |
|------|------|------|
| 入库 | `nm pipeline ingest <file>` | 文本清洗 + 章节切分 |
| 完整流水线 | `nm pipeline full <file>` | 入库 → 分析 → 向量化 → 精调 → 同步 |
| 骨架分析 | `nm pipeline analyze <id>` | 大纲 + 世界观 + 人物 + 标签 |
| 精调 | `nm pipeline refine <id>` | 统计精调 + 数据库同步 |
| 检索 | `nm search <type> <query>` | 章节/人物/世界观/大纲检索 |
| 标签管理 | `nm tags stats` | 查看/添加/审核标签 |
| 素材管理 | `nm material list` | 查看/导入/删除素材 |

## 快速开始

### 1. 安装

```bash
pip install -e .
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 必须填入：
# - DATABASE_URL（PostgreSQL 连接）
# - LLM_API_KEY（OpenAI 或兼容 API）
# - EMBEDDING_API_KEY（向量化 API）
```

### 3. 启动数据库

```bash
make db-up      # 启动 PostgreSQL + pgAdmin
make db-init    # 初始化表结构 + 基础数据
```

或手动启动 PostgreSQL（需安装 pgvector 扩展）。

### 4. 入库小说

```bash
# 完整流程（推荐）
nm pipeline full ./my-novel.txt

# 分步执行
nm pipeline ingest ./my-novel.txt    # 仅入库
nm pipeline analyze nm_xxx           # 仅分析
nm pipeline refine nm_xxx            # 仅精调
```

### 5. 检索

```bash
nm search chapter "开局困境" --limit 10
nm search world --type faction --genre 修仙
nm search outline --genre 科幻 --query "废柴逆袭"
nm search character --archetype 导师
nm search event "雨中告别"
```

## 文档导航

按顺序阅读：

1. **[README.md](README.md)** ← 你在这里
2. **[AGENTS.md](AGENTS.md)**：Agent 操作规则（必读）
3. **[ARCHITECTURE.md](ARCHITECTURE.md)**：系统架构与数据流
4. **[REQUIREMENTS.md](docs/REQUIREMENTS.md)**：业务边界与不做什么
5. **[USER_MANUAL.md](docs/USER_MANUAL.md)**：详细使用手册
6. **[data/schemas/](data/schemas/)**：YAML Schema 定义
7. **[data/tag-system/](data/tag-system/)**：标签分类学体系

## 容错特性

- **断点续传**：章级分析崩溃后自动从断点继续
- **LLM 重试**：网络错误自动重试（指数退避，最多 8 次）
- **默认值兜底**：单步失败不中断流程，使用默认值继续
- **快速失败**：`context_length_exceeded` 不触发无用重试

## 数据产物

完整流水线后生成：

```
data/novels/nm_novel_YYYYMMDD_xxxx/
├── source.txt           # 清洗后的原文
├── meta.yaml            # 元信息
├── chapters.yaml        # 章级分析（摘要、张力、功能、人物）
├── outline/             # 大纲结构
│   ├── structure.yaml
│   ├── plotlines.yaml
│   └── hooks_network.yaml
├── characters/          # 人物档案
│   ├── profiles/
│   └── relations.yaml
├── worldbuilding/       # 世界观
│   ├── factions.yaml
│   ├── geography.yaml
│   └── power_system.yaml
└── tags.yaml            # 小说级标签
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