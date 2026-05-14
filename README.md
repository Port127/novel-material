# Novel Material V2

小说素材管理系统。通过 LLM 对小说进行结构化解析，存储到 YAML + PostgreSQL，提供语义检索服务。

## 设计理念

### 契约驱动设计

本项目采用**契约驱动设计**（Contract-Driven Design）：

```
fields.yaml（单一数据源）
    │
    ├──→ prompts/*.yaml（提示词引用 {{summary_min}}）
    │
    ├──→ validation/models.py（Pydantic 模型读取阈值）
    │
    └──→ validation/quality.py（质量校验读取阈值）
```

一处修改，多处生效：修改 `fields.yaml` 中的阈值，自动同步到提示词、schema 校验、质量校验。

### YAML 为 Source of Truth

分析结果优先落盘为 YAML，数据库是可重建的查询层。

### 章节为最小粒度

不拆分难以定义边界的"事件"或"场景"。详见 [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)。

## 目录结构（核心层）

```
src/novel_material/
├── cli/           # CLI 入口（nm 命令）
├── prompts/       # [契约层] 提示词模板（YAML）
├── schema/        # [契约层] 字段契约（fields.yaml）
├── infra/         # 基础设施 + 服务层
├── pipeline/      # 流水线逻辑
├── search/        # 检索逻辑
├── storage/       # 数据库层
├── tags/          # 标签系统
├── validation/    # 校验层
└── material/      # 素材管理
```

## 功能概览

| 功能 | 命令 | 说明 |
|------|------|------|
| 入库 | `nm pipeline ingest <file>` | 文本清洗 + 章节切分 |
| 总体评估 | `nm pipeline evaluate <id>` | 类型/主线/阶段概要 |
| 章级分析 | `nm pipeline analyze <id>` | 摘要、张力、人物、功能 |
| 骨架分析 | `nm pipeline outline/world/char/tags <id>` | 大纲、世界观、人物、标签 |
| 断点续传 | `nm pipeline continue <id>` | 自动从上次进度继续 |
| 检索 | `nm search <type> <query>` | 章节/人物/世界观/大纲/事件 |
| 标签管理 | `nm tags stats/list/add` | 查看/添加/审核标签 |

## 快速开始

完整操作指南见 [docs/USER_MANUAL.md](docs/USER_MANUAL.md)。

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
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | 开发者 | 系统架构、契约层、服务层、数据流 |
| **[USER_MANUAL.md](docs/USER_MANUAL.md)** | 使用者 | 命令参考、场景指南、故障排查 |
| **[AGENTS.md](AGENTS.md)** | AI Agent | 操作规则、约束、CLI 速览 |
| **[REQUIREMENTS.md](docs/REQUIREMENTS.md)** | 决策者 | 做什么、不做什么、为什么 |

推荐阅读顺序：REQUIREMENTS → ARCHITECTURE → USER_MANUAL → AGENTS。

## 契约层使用示例

### 加载提示词

```python
from novel_material.prompts import load_prompt

prompt = load_prompt("analyze")
print(prompt.system_prompt)  # 已完成模板变量替换
```

### 加载字段契约

```python
from novel_material.schema import load_field, get_threshold

field = load_field("summary")
print(field.min_length)  # 50

threshold = get_threshold("character_thresholds")
print(threshold["core"])  # 50
```

## 数据产物

完整流水线后生成：

```
data/novels/nm_novel_YYYYMMDD_xxxx/
├── source.txt           # 清洗后的原文
├── meta.yaml            # 元信息
├── chapters.yaml        # 章级分析
├── outline/             # 大纲结构
├── characters/          # 人物档案
├── worldbuilding/       # 世界观
├── tags.yaml            # 小说级标签
└── chapter_embeddings.npz  # 向量缓存
```

## 容错特性

内置断点续传、自动重试、默认值兜底。详见 [docs/USER_MANUAL.md](docs/USER_MANUAL.md)。

## 测试

```bash
python -m pytest tests/
```