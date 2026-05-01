# 缺陷与修复路线图 (DEFECTS & ROADMAP)

> **目标读者**：即将修改本代码库的开发者或 AI Agent。动手前请先通读本文档。

> [!WARNING]
> 阶段一至六已完成，原始 P0 致命 Bug、主要架构问题和 Schema 验证均已修复。**系统尚未经过集成验证（阶段七），在准备好数据库环境后，建议先用少量章节小规模试跑，而非直接投入全量生产数据。**

---

## 一、当前状态

| 类别 | 状态 |
|------|------|
| 架构问题 A1-A4 | ✅ 已修复 |
| P0 致命 Bug C1-C3 | ✅ 已修复 |
| P1 严重缺陷 C4-C9 | ✅ 已修复 |
| 标签体系激活 T1 | ❌ 未做 |
| 集成验证 阶段七 | ❌ 未做，需数据库环境 |
| A5 配置割裂 / A6 `material/` 归属 | ⏳ 待决策 |

---

## 二、下一步行动

### 阶段七：集成验证（Integration Testing）

*前置条件：PostgreSQL + pgvector 就绪，LLM API Key 配置完毕。*

| 任务 | 目标 |
|------|------|
| 使用 `material/` 下的真实网文跑完全链路 | 验证端到端闭环 |
| 监控 API 消耗与重试触发情况 | 确认 LLM 调度健壮性 |
| 在数据库层验证结构化 + 向量混合查询 | 确认检索能力 |
| 将 YAML 数据对照 `data/schemas/` 进行结构验证 | 确认 schema 门控实际效果 |

---

### T1. 激活 `data/tag-system/` 标签分类学

`data/tag-system/` 包含 10 篇完整的标签分类学文档（600+ 标签值，含定义、示例、使用规则），目前**没有任何脚本使用它**。`tags.yaml` 只是它的简化摘录，且两者不同步（`chapter_function` 在 Markdown 中有 40+ 值，`tags.yaml` 中只有 20 个）。

**核心影响：**
- `chapter_analyze.py` 让 LLM 选 `chapter_function` 标签，但未提供合法值列表 → LLM 自由发挥 → `quality_check` 大量报"非法标签"
- `generate_tags.py` 已正确注入 `tags.yaml`，但源头值不完整

**建议方案（按需注入，非整个文件夹）：**

| 脚本 | 注入文件 | 目的 |
|------|---------|------|
| `chapter_analyze.py` | `09-chapter-function.md` | 让 LLM 知道哪些章节功能标签合法 |
| `generate_outline.py` | `07-structure.md` | 结构标签上下文 |
| `generate_characters.py` | `05-character.md` | 角色标签上下文 |

同时需要将 `tags.yaml` 补全至与 Markdown 一致，消除断层。

---

### 待决策项（不阻塞其他阶段）

| 项目 | 问题 | 需要的决策 |
|------|------|-----------|
| **A5** 配置割裂 | `config/database.yaml` 无人读取；`requirements.txt` 有 sqlalchemy 但代码用 psycopg2 | 是否统一到单一配置入口，是否切换 ORM |
| **A6** `material/` 归属 | 根目录有原始网文目录，不在 `.gitignore`，不被脚本引用 | 明确用途：作为 ingest 暂存区并加入 `.gitignore`？还是删除？ |

---

## 三、已完成的缺陷修复

### 架构层缺陷（Architectural Issues）

以下问题不是某行代码写错了，而是整体设计上的结构性问题。

#### ~~A1. 流水线执行顺序存在逻辑矛盾~~ ✅ 已修复

`pipeline_full()` 和 `pipeline_analyze()` 的执行顺序已修正为：

```
ingest → chapter_analyze → outline/worldbuilding/characters/tags（基于章级摘要）→ refine → sync
```

`generate_outline.py` 现在读取章级摘要池（`chapters.yaml` 中所有章的摘要拼接，最多 6000 token）作为全局视角输入，原文前 5000 字方案已废弃（保留兜底逻辑：若 chapters.yaml 尚未生成则回退）。`generate_worldbuilding.py` 和 `generate_characters.py` 同步改为优先读取章级摘要池。

#### ~~A2. LLM 调用代码被复制粘贴了 6 次~~ ✅ 已修复

已抽取为 `scripts/core/llm_client.py`，提供统一的 `load_config()` 和 `call_llm()`。原 6 个文件中的重复实现全部删除，改为 `from scripts.core.llm_client import load_config, call_llm`。

#### ~~A3. 所有文件路径硬编码且依赖工作目录~~ ✅ 已修复

已建立 `scripts/core/paths.py`，提供 `PROJECT_ROOT`、`DATA_DIR`、`NOVELS_DIR`、`CONFIG_DIR`、`TAGS_FILE`、`INDEX_FILE` 等常量，全部基于 `__file__` 计算。全项目 15 处 `sys.path.insert(0, os.path.join(...))` hack 已替换为基于 `__file__` 的标准 bootstrap，所有 `Path("data/...")` 硬编码已替换为常量引用。脚本现可从任意目录运行。

#### ~~A4. Schema 定义从未被代码验证~~ ✅ 已修复

`data/schemas/` 下有 YAML Schema 定义文件，规定了 `meta.yaml`、`chapters.yaml` 等的字段格式。但原先没有一行代码读取这些 schema 并校验数据，`quality_check.py` 只做了摘要长度检查。

**修复方案：**
- 新建 `scripts/utils/schema_validator.py`（pydantic 模型：`MetaModel` / `ChapterEntryModel` / `NovelTagsModel`）
- 重写 `quality_check.py`：schema 结构校验 + 覆盖率检查 + 摘要质量检查三层叠加
- `chapter_analyze.py` 全部分析完成后自动调用 `run_quality_check()`
- `sync_db.py` 同步前调用 `_precheck_schema()`，schema 不通过则终止同步

---

### 代码层致命缺陷（P0 — 阻断主流程）

#### ~~C1. `ingest.py`：缺少文本预处理层~~ ✅ 已修复

已新建 `scripts/core/preprocess.py`，实现完整预处理流水线：编码归一化（NFC）→ 去广告水印 → 中文数字转阿拉伯数字（支持到亿级）→ 空白清理。`ingest.py` 在章节正则匹配前调用 `preprocess()`，正则层本身保持简洁。

#### ~~C2. `ingest.py`：未定义变量导致崩溃~~ ✅ 已修复

`print(f"入库完成: {material_dir}")` → `print(f"入库完成: {novel_dir}")`

#### ~~C3. `sync_db.py`：JSONB 字段写入 YAML 格式字符串~~ ✅ 已修复

所有 `yaml.dump(...)` 替换为 `json.dumps(..., ensure_ascii=False)`，涉及 `tags`、`psychology`、`properties` 三个 JSONB 字段。同时将单一大事务拆分为按模块独立提交（meta / chapters / outline / characters / worldbuilding 各自 commit），章节同步进一步按 50 章批量提交。

---

### 代码层严重缺陷（P1 — 高业务风险）

#### ~~C4. `chapter_analyze.py`：LLM 裸调 + 零容错 + 无断点续传~~ ✅ 已修复

- **重试**：`llm_client.call_llm` 引入 `tenacity` 指数退避重试，最多 5 次，覆盖网络超时/限流/5xx
- **断点续传**：每章分析完立即调用 `_append_chapter()` 写入磁盘；重启时自动跳过已完成章节
- **单章失败不中断**：`try/except` 捕获耗尽重试的异常，打印警告后继续处理下一章

#### ~~C5. `chapter_analyze.py`：3000 字符硬截断~~ ✅ 已修复

`llm_client.truncate_to_tokens()` 使用 tiktoken 精确计算 Token 数（上限 1800 tokens），按语义单元截断，不在词语中间截断。不再有硬截字符的方式。

#### ~~C6. `generate_outline.py`：5000 字定终身~~ ✅ 已修复（随 A1 修复同步解决）

`generate_outline.py` 现在读取章级摘要池（`_build_summary_pool()`），最多 6000 tokens，覆盖全书摘要。与 A1 流水线顺序修正配合，大纲生成时已有完整全书视角。

#### ~~C7. 向量化工具已就绪但未被集成~~ ✅ 已修复

新建 `scripts/core/embed_chapters.py`，支持断点续传、批量向量化，写入 `chapter_embeddings.yaml`。流水线在 `chapter_analyze` 之后加入 `embed_chapters` 步骤。`sync_db.py` 的 `_sync_chapters()` 读取向量文件并写入数据库 `embedding` 字段（向量不存在时跳过该字段，向后兼容）。

#### ~~C8. 检索脚本无 CLI 参数解析~~ ✅ 已修复

6 个 `scripts/search/` 脚本均已加入 `click` 装饰器，实现完整 CLI 参数解析。带位置参数的脚本（`search_chapter.py`、`search_event.py`）使用 `@click.argument`，其余使用 `@click.option`，所有脚本支持 `--help`。

#### ~~C9. `pipeline.py` 缺少 `ingest` 子命令~~ ✅ 已修复

已添加 `pipeline_ingest()` 函数和 `ingest` 子命令，现可通过 `python scripts/pipeline.py ingest <路径>` 独立执行入库操作。

---

## 四、修复路线图（已完成阶段）

### ~~阶段一：基础设施整固（Infrastructure）~~ ✅ 已完成

*目标：消灭复制粘贴，统一路径和配置，为后续所有修复打下基础。*

| 任务 | 解决的缺陷 |
|------|-----------|
| 抽取 `scripts/core/llm_client.py`（统一 `call_llm` + `load_config`）| A2 |
| 建立 `scripts/core/paths.py`（项目根路径自动定位）| A3 |
| 所有脚本改为从共享模块 import，移除 15 处 `sys.path.insert` | A3 |

### ~~阶段二：打通输入输出管道（Core Pipeline）~~ ✅ 已完成

*目标：让数据能进来（ingest）、能存进去（sync）。*

| 任务 | 解决的缺陷 |
|------|-----------|
| 新建 `scripts/core/preprocess.py` 预处理模块（中文数字转换、去广告、编码归一化），在正则匹配前调用 | C1 |
| 修复 `material_dir` → `novel_dir` | C2 |
| `sync_db.py` 中 `yaml.dump` → `json.dumps` | C3 |
| 拆分数据库大事务为按章节批量提交 | 架构优化 |
| 为 `pipeline.py` 添加 `ingest` 子命令 | C9 |

### ~~阶段三：LLM 调用工业化（LLM Resiliency）~~ ✅ 已完成

*目标：所有大模型调用具备重试、断点续传和智能上下文管理能力。*

| 任务 | 解决的缺陷 |
|------|-----------|
| 在 `llm_client.py` 中引入 `tenacity` 指数退避重试 | C4 |
| `chapter_analyze.py` 改为边分析边写入（断点续传）| C4 |
| 引入 `tiktoken` 动态 Token 计算，废弃 `content[:3000]` 硬截断 | C5 |
| **修正流水线执行顺序**：章级分析前置，大纲/世界观/人物/标签后置 | A1, C6 |
| `generate_outline.py` 改为读取章级摘要池，而非前 5000 字原文 | C6 |

### ~~阶段四：补齐向量与 CLI（Embeddings & CLI）~~ ✅ 已完成

*目标：语义检索从空壳变为可用，所有脚本真正支持命令行调用。*

| 任务 | 解决的缺陷 |
|------|-----------|
| 新建 `embed_chapters.py`，流水线加入 embedding 步骤 | C7 |
| `sync_db.py` 中写入 `embedding` 向量字段 | C7 |
| 为所有 `scripts/search/` 脚本引入 `click` CLI 参数解析 | C8 |

### ~~阶段五：补全 A1 修复 + 文档同步（A1 Completion & Docs）~~ ✅ 已完成

*目标：让 A1 的修复效果覆盖所有骨架分析脚本，并清理已过期的文档描述。*

| 任务 | 关联问题 |
|------|---------|
| `generate_worldbuilding.py` 改为读取章级摘要池（兜底逻辑与 outline 一致）| A1 补全 |
| `generate_characters.py` 改为读取章级摘要池 | A1 补全 |
| 更新 `AGENTS.md` 中 4 处过期 `[WIP]` 标记 | 文档同步 |
| 更新文档顶部横幅，反映当前真实状态 | 文档同步 |

### ~~阶段六：Schema 数据验证（Schema Validation）~~ ✅ 已完成

*目标：让 `data/schemas/` 下的 schema 真正发挥约束作用，LLM 输出的脏数据在写入磁盘前被拦截。*

| 任务 | 解决的缺陷 |
|------|-----------|
| 新建 `scripts/utils/schema_validator.py`（pydantic 模型）| A4 |
| 重写 `quality_check.py`，整合 schema 结构校验 + 覆盖率 + 摘要质量 | A4 |
| `chapter_analyze.py` 完成后自动调用 `run_quality_check()` | A4 |
| `sync_db.py` 同步前调用 `_precheck_schema()`，不通过则终止 | A4 |

---

## 五、附录：Schema 清理记录

从 `data/schemas/` 移除 2 份 V1 遗产（移至 `docs/research/` 归档）：

| 文件 | 原因 |
|------|------|
| `event-unit.schema.yaml` | 定义 `ev_xxx.yaml` 事件文件，V2 硬规则禁止事件粒度拆分 |
| `plot-index.schema.yaml` | 依赖事件计数统计，V2 不产出此数据 |

新增 V2 缺失的核心 schema：

| 文件 | 描述 |
|------|------|
| `data/schemas/chapters.schema.yaml` | 定义 `chapters.yaml` 字段结构，对应 `ChapterEntryModel` |
