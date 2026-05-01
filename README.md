# Novel Material V2

小说写作参考检索库。本项目旨在通过 LLM 对小说进行结构化解析（大纲、世界观、章级分析等），并将数据存入 YAML 与 PostgreSQL 中，供大模型 Agent 在写作时进行语义和结构化检索。

> ℹ️ **项目当前状态：核心修复已完成，待集成验证**
> 阶段一至六的修复工作已完成：LLM 重试/断点续传、文本预处理、Schema 验证、向量化集成、CLI 参数解析均已就位。**系统尚未进行全链路集成验证**，建议在准备好数据库环境后先用少量章节试跑。
> 详情请见：[缺陷与路线图 (DEFECTS & ROADMAP)](docs/DEFECTS_AND_ROADMAP.md)

## 核心设计理念

1.  **AI 协作优先**：本项目不是给人提供 Web 界面的，而是给 AI Agent 准备的检索后备库。详细规则见 [AGENTS.md](AGENTS.md)。
2.  **YAML 为 Source of Truth**：一切分析结果优先落盘为 YAML，数据库仅仅是随时可以重建的查询层。
3.  **不作过度拆分**：坚持以“章节”为最小粒度，拒绝拆分难以定义边界的“事件”或“场景”。详见 [REQUIREMENTS.md](docs/REQUIREMENTS.md)。

## 当前可用能力

*   **入库 (Ingest)**：文本预处理（NFC 归一化、去广告水印、中文数字→阿拉伯数字）+ 章节正则切分，生成 `chapter_index.yaml`。
*   **章级分析 (Chapter Analyze)**：LLM 逐章生成摘要、出场人物、功能标签、张力值，支持断点续传，自动重试，完成后触发 Schema 质量校验。
*   **骨架分析 (Analyze)**：基于章级摘要池生成大纲、世界观、人物图谱、小说级标签（不再依赖原文截断）。
*   **向量化 (Embed)**：章级摘要向量化，写入 `chapter_embeddings.yaml`，并随数据库同步持久化。
*   **数据库同步 (Sync)**：将 YAML 数据同步至 PostgreSQL，同步前执行 Schema 预检门控。
*   **检索 (Search)**：6 个维度的检索脚本，均支持 `click` CLI 参数解析。

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

```bash
# 独立入库（预处理 + 章节切分）
python scripts/pipeline.py ingest path/to/novel.txt

# 完整流水线（入库 → 章级分析 → 向量化 → 骨架分析 → 精调 → 同步）
python scripts/pipeline.py full path/to/novel.txt

# 分步：仅分析（章级 → 大纲 → 世界观 → 人物 → 标签）
python scripts/pipeline.py analyze <material_id>

# 分步：精调 + 同步数据库
python scripts/pipeline.py finalize <material_id>
```

> **注意**：中文章节标题（如"第一百零三章"）会在预处理阶段自动转换为阿拉伯数字格式，无需手动处理。LLM 调用支持自动重试（最多 5 次指数退避），章级分析支持断点续传。

### 4. 检索调用

```bash
python scripts/search/search_chapter.py "开局困境写法" --limit 10
python scripts/search/search_world.py --type faction --genre 修仙 --limit 10
python scripts/search/search_outline.py --genre 修仙 --query "废柴逆袭"
python scripts/search/search_character.py --archetype 导师 --genre 修仙
python scripts/search/search_event.py "雨中告别的写法" --limit 10
python scripts/search/search_detail.py --genre 悬疑 --act 2
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
