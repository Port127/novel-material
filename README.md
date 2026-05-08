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

或使用多服务商配置：

```bash
# config/providers.yaml
default_provider: deepseek
providers:
  - name: deepseek
    model: deepseek-chat
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
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
nm pipeline analyze nm_xxx           # 章级分析
nm pipeline outline nm_xxx           # 大纲生成
nm pipeline worldbuilding nm_xxx     # 世界观提取
nm pipeline characters nm_xxx        # 人物提取
nm pipeline tags nm_xxx              # 标签生成
nm pipeline refine nm_xxx            # 精调

# 指定服务商
nm pipeline analyze nm_xxx --provider deepseek

# 指定章节范围
nm pipeline analyze nm_xxx --start 100 --end 200
```

### 5. 检索

```bash
# 章节检索（向量语义）
nm search chapter "开局困境" --limit 10

# 大纲检索
nm search outline --genre 玄幻 --query "废柴逆袭"

# 人物检索
nm search character --archetype 导师 --role 主角

# 世界观检索
nm search world "宗门" --dimension faction --limit 10

# 事件检索
nm search event "雨中告别" --setting 城市 --emotion 悲伤
```

### 6. 标签管理

```bash
nm tags stats                       # 标签统计
nm tags list --dimension element    # 按维度列出
nm tags add element 血脉 xuanhuan --group 设定元素  # 添加标签
nm tags review --auto               # 自动审批高频标签
```

### 7. 从断点继续

```bash
nm pipeline status nm_xxx           # 查看进度
nm pipeline continue nm_xxx         # 自动继续未完成阶段
```

## 文档导航

按顺序阅读：

1. **[README.md](README.md)** ← 你在这里
2. **[AGENTS.md](AGENTS.md)**：Agent 操作规则（必读）
3. **[ARCHITECTURE.md](ARCHITECTURE.md)**：系统架构与数据流
4. **[USER_MANUAL.md](USER_MANUAL.md)**：详细使用手册
5. **[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)**：业务边界与不做什么
6. **[data/schemas/](data/schemas/)**：YAML Schema 定义
7. **[data/tag-system/](data/tag-system/)**：标签分类学体系

## 容错特性

- **断点续传**：章级分析崩溃后自动从断点继续，无需重做
- **LLM 重试**：网络错误自动重试（指数退避，最多 8 次）
- **默认值兜底**：单步失败不中断流程，使用默认值继续
- **快速失败**：`context_length_exceeded` 不触发无用重试
- **JSON 重试**：解析失败自动翻倍 `max_tokens` 重试

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

支持配置多个 LLM 服务商：

```yaml
# config/providers.yaml
default_provider: qwen
providers:
  - name: qwen
    model: qwen3.6-plus
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    thinking_format: dashscope
  - name: deepseek
    model: deepseek-chat
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    thinking_format: openai
```

使用时通过 `--provider` 参数切换：
```bash
nm pipeline analyze nm_xxx --provider deepseek
```

## 测试

```bash
python -m pytest tests/
```