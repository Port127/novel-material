# 缺陷与修复路线图 (DEFECTS & ROADMAP)

> **本文档的目标读者**：即将对本代码库进行修改的开发者或 AI Agent。
> 在动手写任何新功能之前，请先通读本文档，理解当前系统的真实状态。

> [!CAUTION]
> 当前代码库存在**架构设计缺陷**和**多处致命代码 Bug**。在这些问题修复之前，请绝对不要将大规模生产数据投入 Pipeline，否则将引发系统崩溃并产生大量无效 API 费用。

---

## 一、架构层缺陷（Architectural Issues）

以下问题不是某行代码写错了，而是整体设计上的结构性问题。它们会随着项目规模扩大而持续恶化，必须在功能开发之前解决。

### A1. 流水线执行顺序存在逻辑矛盾

当前 `pipeline_full()` 的执行顺序为：

```
ingest → outline → worldbuilding → characters → tags → chapter_analyze → sync
```

**问题**：`generate_outline.py` 只读取全书前 5000 个字符来判断三幕式结构和全书基调。但真正能提供全书视角的章级摘要（`chapters.yaml`）要等到 `chapter_analyze` 完成后才会存在。这等于让一个人读了两页序言就来写全书大纲。

**正确的顺序应为**：
```
ingest → chapter_analyze → outline/worldbuilding/characters/tags（基于章级摘要）→ refine → sync
```

先完成章级分析，再用摘要池作为大模型的全局视角输入，才能生成有意义的大纲和世界观。

### A2. LLM 调用代码被复制粘贴了 6 次

`call_llm()` 和 `load_config()` 这两个完全相同的函数分别出现在以下 6 个文件中：

- `scripts/core/chapter_analyze.py`
- `scripts/analyze/generate_outline.py`
- `scripts/analyze/generate_worldbuilding.py`
- `scripts/analyze/generate_characters.py`
- `scripts/analyze/generate_tags.py`
- `scripts/utils/refine.py`

**后果**：当我们需要引入重试机制（`tenacity`）、Token 计算（`tiktoken`）、或统一的错误处理时，必须修改 6 个地方。漏改任何一个，那个脚本就会继续裸调 API。

**解决方案**：抽取为 `scripts/core/llm_client.py`，所有脚本统一 import。

### A3. 所有文件路径硬编码且依赖工作目录

全项目 18 处 `sys.path.insert(0, ...)` hack，以及大量 `Path("data/novels")`、`Path("config")` 等相对于 CWD 的硬编码路径。

**后果**：所有脚本**必须从项目根目录运行**。如果从 `scripts/` 目录或任何其他位置执行，会静默找不到文件或找到错误的文件。

**解决方案**：建立 `scripts/core/paths.py`，基于 `__file__` 自动定位项目根目录，统一提供 `PROJECT_ROOT`、`DATA_DIR`、`CONFIG_DIR` 等常量。

### A4. Schema 定义从未被代码验证

`data/schemas/` 下有 11 份 YAML Schema 定义文件，规定了 `meta.yaml`、`chapters.yaml` 等的字段格式。但纵观全项目，**没有一行代码读取这些 schema 并校验数据**。`quality_check.py` 只做了摘要长度检查，远未达到 schema 级别的结构验证。

**后果**：schema 是空头支票。LLM 生成的 YAML 可能缺少必填字段、类型错误，但系统毫无感知，脏数据会一路流入数据库。

### A5. 配置体系割裂

| 配置来源 | 使用方 | 格式 |
|----------|--------|------|
| `.env` | `sync_db.py`、search 脚本 | `DATABASE_URL` 环境变量 |
| `config/llm.yaml` | 6 个 LLM 调用脚本 | YAML |
| `config/embedding.yaml` | `embedding.py` | YAML |
| `config/database.yaml` | 无人使用 | YAML |

`requirements.txt` 中引入了 `sqlalchemy`，但实际代码全部使用裸 `psycopg2`。`config/database.yaml` 定义了连接池参数（`pool_size: 5`），但没有任何代码读取它。

### A6. 根目录存在未纳管的 `material/` 目录

项目根目录有一个 `material/` 文件夹，内含两本网文原文 txt（约 20MB）。它不在 `data/` 中，不被任何脚本引用，不在 `.gitignore` 中，也不在任何文档中出现。需要明确其归属：是原始素材的暂存区？还是被遗忘的测试文件？

---

## 二、代码层致命缺陷（P0 — 阻断主流程）

以下 Bug 会直接导致程序崩溃或数据无法写入，必须最优先修复。

### C1. `ingest.py`：缺少文本预处理层，章节正则直接裸匹配原文

**位置**：`scripts/core/ingest.py` → `detect_chapter_pattern()`

正则 `r"^\s*(?:第\s*\d+\s*[章节回卷篇]|楔子|引子|序章|终章|尾声)\s*"` 中的 `\d+` 只匹配阿拉伯数字。

**影响**：使用“第一百二十三章”格式的中文网文（占绝大多数）会被判定为无章节，切分失败，整个 Pipeline 停摆。

**根因**：`ingest.py` 缺少文本预处理层。正确的设计不是“让正则兼容所有格式”，而是在正则匹配之前新增一个预处理步骤：

```
原文 → 预处理（中文数字→阿拉伯、去广告、统一编码）→ 章节正则匹配 → 切分
```

这样正则层保持简洁，脏活由预处理层承担。

### C2. `ingest.py`：未定义变量导致崩溃

**位置**：`scripts/core/ingest.py` 第 123 行

`print(f"入库完成: {material_dir}")` 中的 `material_dir` 从未被定义（正确变量名为 `novel_dir`），必然抛出 `NameError`。

### C3. `sync_db.py`：JSONB 字段写入 YAML 格式字符串

**位置**：`scripts/core/sync_db.py` 多处

向 PostgreSQL 的 `JSONB` 字段插入数据时使用了 `yaml.dump()`。YAML 格式字符串（含换行、缩进）并非合法 JSON，数据库会直接拒绝写入并回滚事务。

**修复**：替换为 `json.dumps(..., ensure_ascii=False)`。

---

## 三、代码层严重缺陷（P1 — 高业务风险）

以下问题不会立即崩溃，但会导致数据质量严重下降或产生巨额浪费。

### C4. `chapter_analyze.py`：LLM 裸调 + 零容错 + 无断点续传

在 `for` 循环中逐章调用 OpenAI API，无 `try/except`，无重试。所有结果全部在内存中累积，循环结束后才一次性写入 `chapters.yaml`。

**后果**：处理 500 章的小说时，如果第 499 章遇到 API 限流或网络超时，之前所有章的 Token 费和时间全部作废。

### C5. `chapter_analyze.py`：3000 字符硬截断

`content[:3000]` 直接砍掉章节末尾。网文章末通常包含最重要的"钩子"和转折，截断后 LLM 无法准确判断 `tension_level` 和 `key_plot_point`。

### C6. `generate_outline.py`：5000 字定终身

`source_text = f.read()[:5000]` — 用全书开头 5000 字符判断整部小说的结构类型和主题基调。这个问题与 A1 相关联：即使修复了截断长度，只要执行顺序不改，大纲提取永远缺乏全局视野。

### C7. 向量化工具已就绪但未被集成

`scripts/core/embedding.py` 提供了完整的 `get_embedding()` 和 `get_embeddings_batch()` 函数（支持 OpenAI 和 BGE 两种 provider）。但没有任何流水线步骤调用它，`sync_db.py` 也未将向量写入数据库的 `vector(1024)` 字段。语义检索能力完全悬空。

### C8. 检索脚本无 CLI 参数解析

`scripts/search/` 下 6 个脚本的 `__main__` 均为硬编码的函数调用示例，未使用 `argparse` 或 `click`。Agent 按照 `AGENTS.md` 中记载的命令行格式调用时，参数不会被解析。

### C9. `pipeline.py` 缺少 `ingest` 子命令

`pipeline.py` 只有 `full`、`analyze`、`finalize` 三个模式。无法单独执行入库操作，与 `AGENTS.md` 中记载的 `python scripts/pipeline.py ingest [路径]` 直接矛盾。

---

## 四、修复路线图 (Roadmap)

基于以上全部缺陷，我们当前的首要目标**不是添加新功能，而是让系统能真正跑完一个闭环**。以下按依赖关系排列，必须严格按顺序执行。

### 阶段一：基础设施整固（Infrastructure）

*目标：消灭复制粘贴，统一路径和配置，为后续所有修复打下基础。*

这是其他所有阶段的前置条件。如果不先完成基础设施整固，后续每个修复都会在 6 个文件中重复操作。

| 任务 | 解决的缺陷 |
|------|-----------|
| 抽取 `scripts/core/llm_client.py`（统一 `call_llm` + `load_config`）| A2 |
| 建立 `scripts/core/paths.py`（项目根路径自动定位）| A3 |
| 所有脚本改为从共享模块 import，移除 18 处 `sys.path.insert` | A3 |

### 阶段二：打通输入输出管道（Core Pipeline）

*目标：让数据能进来（ingest）、能存进去（sync）。*

| 任务 | 解决的缺陷 |
|------|-----------|
| 新建 `scripts/core/preprocess.py` 预处理模块（中文数字转换、去广告、编码归一化），在正则匹配前调用 | C1 |
| 修复 `material_dir` → `novel_dir` | C2 |
| `sync_db.py` 中 `yaml.dump` → `json.dumps` | C3 |
| 拆分数据库大事务为按章节批量提交 | 架构优化 |
| 为 `pipeline.py` 添加 `ingest` 子命令 | C9 |

### 阶段三：LLM 调用工业化（LLM Resiliency）

*目标：所有大模型调用具备重试、断点续传和智能上下文管理能力。*

由于阶段一已经抽取了共享的 `llm_client.py`，以下改造只需在一个地方完成：

| 任务 | 解决的缺陷 |
|------|-----------|
| 在 `llm_client.py` 中引入 `tenacity` 指数退避重试 | C4 |
| `chapter_analyze.py` 改为边分析边写入（断点续传）| C4 |
| 引入 `tiktoken` 动态 Token 计算，废弃 `content[:3000]` 硬截断 | C5 |
| **修正流水线执行顺序**：章级分析前置，大纲/世界观/人物/标签后置 | A1, C6 |
| `generate_outline.py` 改为读取章级摘要池，而非前 5000 字原文 | C6 |

### 阶段四：补齐向量与 CLI（Embeddings & CLI）

*目标：语义检索从空壳变为可用，所有脚本真正支持命令行调用。*

| 任务 | 解决的缺陷 |
|------|-----------|
| 在流水线中新增 embedding 步骤，集成已有的 `embedding.py` | C7 |
| `sync_db.py` 中填入 `vector(1024)` 字段 | C7 |
| 为所有 `scripts/search/` 脚本引入 `click` CLI 参数解析 | C8 |

### 阶段五：集成验证（Integration Testing）

| 任务 | 目标 |
|------|------|
| 使用 `material/` 下的真实网文跑完全链路 | 验证端到端闭环 |
| 监控 API 消耗与重试触发情况 | 确认 LLM 调度健壮性 |
| 在数据库层验证结构化 + 向量混合查询 | 确认检索能力 |
| 将 YAML 数据对照 `data/schemas/` 进行结构验证 | A4 |
