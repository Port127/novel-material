# Novel Material V2

小说写作参考检索库。本项目旨在通过 LLM 对小说进行结构化解析（大纲、世界观、章级分析等），并将数据存入 YAML 与 PostgreSQL 中，供大模型 Agent 在写作时进行语义和结构化检索。

> ⚠️ **项目当前状态：开发中期（高危阶段）**
> 核心框架和流水线脚本已经搭建，但代码中存在**大量严重的业务 Bug 和 0 容错的 LLM 调用**。请勿在未经修复的情况下投入海量数据进行生产级构建，否则将面临 API 费用浪费和数据崩溃的风险。
> 详情请见：[缺陷与路线图 (DEFECTS & ROADMAP)](docs/DEFECTS_AND_ROADMAP.md)

## 核心设计理念

1.  **AI 协作优先**：本项目不是给人提供 Web 界面的，而是给 AI Agent 准备的检索后备库。详细规则见 [AGENTS.md](AGENTS.md)。
2.  **YAML 为 Source of Truth**：一切分析结果优先落盘为 YAML，数据库仅仅是随时可以重建的查询层。
3.  **不作过度拆分**：坚持以“章节”为最小粒度，拒绝拆分难以定义边界的“事件”或“场景”。详见 [REQUIREMENTS.md](docs/REQUIREMENTS.md)。

## 当前可用能力

目前代码库**已经跑通或搭建好骨架**的部分：

*   **入库 (Ingest)**：能对文本文档进行初步的章节切分（*注：目前仅支持阿拉伯数字章节正则*）。
*   **骨架分析 (Analyze)**：能够通过调用 LLM（需配置 OpenAI API）初步生成小说设定、人物图谱和大纲。
*   **章级分析 (Chapter Analyze)**：能对单章生成摘要并打上结构标签。
*   **数据库同步 (Sync)**：提供脚本将部分 YAML 数据同步至 PostgreSQL 中。
*   **检索路由 (Search)**：已建立各个维度的检索 CLI 入口脚本。

## 运行方式 (Quick Start)

### 1. 环境准备

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 准备环境变量
cp .env.example .env
# 必须在 .env 中填入有效的 DATABASE_URL 和 LLM_API_KEY
```

### 2. 数据库初始化

你需要一个安装了 `pgvector` 扩展的 PostgreSQL 数据库：

```bash
# 初始化表结构和索引
python scripts/core/init_db.py
```

### 3. 流水线执行

> **注意**：执行前请确保您的网文源文件使用的是 `第1章`、`第1回` 等阿拉伯数字格式，否则会直接切分失败。

```bash
# [高危] 完整流水线（入库 → LLM分析 → 同步数据库）
# 极易因为 LLM 网络超时而崩溃，建议慎用
python scripts/pipeline.py full path/to/novel.txt

# 分步执行：针对已入库素材进行 LLM 分析
python scripts/pipeline.py analyze <material_id>

# 分步执行：精调 + 同步数据库
python scripts/pipeline.py finalize <material_id>
```

> ⚠️ **当前不存在独立的 `ingest` 子命令**。入库操作目前只能通过 `full` 触发，或直接调用底层函数 `scripts/core/ingest.py`。

### 4. 检索调用

检索脚本位于 `scripts/search/` 下。

> ⚠️ **当前所有 search 脚本均未实现 CLI 参数解析**（无 argparse/click），`__main__` 中的查询条件为硬编码示例。实际使用需修改源码中的函数调用参数，或作为 Python 模块 import 使用。

```python
# 示例：在 Python 中调用
from scripts.search.search_chapter import search_chapters
search_chapters(query="开局困境写法", genre="修仙", limit=10)
```

## 文档导航

要深入了解本项目，请务必按顺序阅读以下文档：

1.  **[业务需求边界 (REQUIREMENTS.md)](docs/REQUIREMENTS.md)**：我们为什么要做这个项目，以及**坚决不做**什么。
2.  **[真实架构与数据流 (ARCHITECTURE.md)](ARCHITECTURE.md)**：系统的全貌、数据流向以及 Agent 的协作机制。
3.  **[Agent 契约 (AGENTS.md)](AGENTS.md)**：Agent 操作本代码库的绝对规则。
4.  **[缺陷与路线图 (DEFECTS_AND_ROADMAP.md)](docs/DEFECTS_AND_ROADMAP.md)**：**重中之重！** 记录了当前代码库急需修复的各种坑点。
5.  **[数据 Schema 定义 (data/schemas/)](data/schemas/)**：所有 YAML 数据文件的字段契约（meta、outline、characters、worldbuilding 等）。
6.  **[标签分类学体系 (data/tag-system/)](data/tag-system/)**：600+ 标签的完整分类学规格，同时作为 LLM 标签标注时的 Prompt 素材。
7.  **[历史研究与决策记录 (docs/research/)](docs/research/)**：V1→V2 架构重设计的推导过程与迁移指南。
