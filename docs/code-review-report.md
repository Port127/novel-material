# Project Review Report

**日期**: 2026-06-16  
**范围**: 全项目（`src/novel_material/`, `tests/`, `docs/`, `config/`, `data/schemas/`）  
**主要语言**: Python 3.10+  
**审查方式**: 结构扫描、关键路径人工审查、`pytest`、`compileall`、外部 RAG/向量检索项目对照  

## 摘要

Novel Material V2 的产品定位和架构分层是清楚的：它不是单纯的“小说全文搜索”，而是把小说拆成入库、章级分析、向量化、骨架抽取、标签和 PostgreSQL 查询层。这个方向适合“写作参考素材库”，优于只把原文切块塞进向量库。

更大的问题在工程成熟度：当前文档、CLI、搜索函数、数据库 schema、测试覆盖之间已经出现明显漂移；检索层存在用户可见的返回契约错误；现有测试不通过；向量检索设计在 `vector(4096)` 下无法建 ANN 索引，会随着素材增长迅速退化；项目缺少 RAG/检索质量评测闭环。

## 优点

1. **产品边界清晰**  
   `docs/REQUIREMENTS.md`、`ARCHITECTURE.md`、`docs/USER_MANUAL.md` 明确区分了入库、分析、骨架、检索、标签、存储，不是随手堆脚本。

2. **契约驱动意识较好**  
   `src/novel_material/schema/fields.yaml`、`FieldSchema`、Pydantic 校验和 prompt 模板变量已经形成“字段阈值集中管理”的雏形。

3. **长流程韧性设计不错**  
   章节独立文件 `chapters/{n}.yaml`、断点续传、失败章节重分析、`PipelineRunner` 运行历史、API token 记录，这些都符合长篇小说处理的真实痛点。

4. **LLM 输出质量有防御机制**  
   动态温度、thinking 管理、摘要相似度检测、短摘要自动重试，说明项目已经遇到并处理过“后期章节模式化输出”的实际问题。

5. **结构化数据价值高于纯向量化**  
   章节摘要、张力、人物、世界观、结构角色、标签进入 PostgreSQL，比仅做 embedding 更适合写作检索、筛选和统计。

## 主要缺陷与改进点

### Critical 1: 现有测试不通过

- **位置**: `tests/pipeline/test_ingest.py:112`, `src/novel_material/pipeline/ingest.py:129`
- **现象**: `python -m pytest` 结果为 1 failed, 49 passed, 1 skipped。
- **问题**: 测试期望字数统计保留空格，代码实现为去除全部空白。当前失败虽小，但它说明“章节字数”契约没有被统一定义。后续会影响 meta 字数、章节过滤、质量统计和成本估算。
- **建议**:
  - 在 `fields.yaml` 或专门文档中定义 `word_count` 口径：是否包含标题、空格、标点、换行。
  - 修改测试或实现二选一，不要靠注释解释分歧。
  - 把 `pytest` 加入 CI 阻断。

### Critical 2: `nm search` 包装层与底层函数返回契约断裂

- **位置**: `src/novel_material/cli/search.py:22`, `src/novel_material/cli/search.py:52`, `src/novel_material/cli/search.py:82`, `src/novel_material/cli/search.py:116`
- **位置**: `src/novel_material/search/chapter.py:155-181`, `src/novel_material/search/outline.py:94-113`, `src/novel_material/search/character.py:103-124`, `src/novel_material/search/world.py:117-135`
- **问题**: CLI 层把 `search_*` 当成返回 `results` 的服务函数；底层实际只打印结果并隐式返回 `None`。结果是：底层可能打印“找到 N 条”，CLI 随后又输出“未找到匹配结果”。
- **建议**:
  - 搜索模块只负责查询并 `return list[dict]`。
  - CLI 层统一负责 Rich 表格展示。
  - 为 `nm search chapter/outline/character/world` 增加 Typer runner 测试。

### Critical 3: 向量检索会随数据规模退化为全表扫描

- **位置**: `src/novel_material/storage/schema.sql:182-189`
- **问题**: schema 注释明确 `vector(4096)` 不能建 IVFFLAT/HNSW，当前向量搜索走全表扫描。这与 README/需求里“多素材、长篇 1000+ 章”的目标冲突。
- **建议**:
  - 方案 A: 换用可建索引的低维 embedding（如 768/1024/1536/2000 内）。
  - 方案 B: 继续 4096 维但迁移 Qdrant/Milvus/pgvector halfvec/sparsevec 组合方案。
  - 方案 C: 做两阶段检索：PostgreSQL 结构过滤先缩小候选，再小集合向量重排。
  - 增加 `EXPLAIN ANALYZE` 基准：1k、10k、100k 章节下 P50/P95 延迟。

### Critical 4: 缺少检索质量评测闭环

- **位置**: 当前无 `tests/search/`、无检索基准集、无 RAG 指标脚本。
- **问题**: 项目核心价值是“素材检索能不能帮写作”，但没有 golden queries、人工相关性标注、Recall@K、MRR、nDCG、失败案例归档。现在只能凭主观感觉调 prompt 和 embedding。
- **建议**:
  - 建立 `eval/search_queries.yaml`：查询、期望章节/人物/世界观实体、过滤条件。
  - 指标至少包含 Recall@5、MRR、nDCG、结构过滤命中率、无结果率。
  - 每次调整 prompt、embedding model、chunk 策略后跑回归。

### Suggestion 5: 配置来源分散，embedding 未纳入 `providers.yaml`

- **位置**: `src/novel_material/infra/config_service.py:15-125`, `src/novel_material/infra/embedding.py:11-20`
- **问题**: LLM 走 `settings.yaml + providers.yaml`，embedding 仍直接读 `.env`。这会让“模型、维度、base_url、provider”的实际生效值不透明，也难以在一次 pipeline 运行中记录完整 provenance。
- **建议**:
  - 增加统一 `embedding` 配置服务。
  - 在 run history/meta 中记录 LLM provider/model、embedding provider/model/dimension。
  - 启动时校验 embedding 维度与 DB schema 一致。

### Suggestion 6: 文档与实现存在漂移

- **位置**: `ARCHITECTURE.md:17-113`, `docs/USER_MANUAL.md:47`, `src/novel_material/schema/fields_loader.py:9`
- **问题**: 部分文档仍写根目录 `schema/fields.yaml`、`prompts/*.yaml`，实际文件在 `src/novel_material/schema/fields.yaml` 和 `src/novel_material/prompts/*.yaml`。AGENTS.md 也有旧路径表述。
- **建议**:
  - 统一所有文档路径。
  - 增加文档检查脚本，至少验证关键路径存在。

### Suggestion 7: 函数副作用偏重，服务层与展示层仍耦合

- **位置**: `src/novel_material/search/*.py`, `src/novel_material/storage/init_db.py`, `src/novel_material/material/delete.py`
- **问题**: 很多服务函数直接 `print`、读 env、连接数据库、格式化输出，难以单元测试和复用。
- **建议**:
  - 形成三层：repository/query 返回数据、service 组合业务、CLI 展示。
  - 搜索函数支持注入 connection/config，测试时用 fake connection。

### Suggestion 8: 自动修复会触发 LLM 重分析，风险较高

- **位置**: `src/novel_material/storage/sync_core.py:128-167`
- **问题**: `nm storage sync` 预检失败后会自动调用 LLM 修复章节。虽然方便，但同步命令变成“会产生新分析结果、消耗 API、改变 YAML”的写操作，用户预期不一定一致。
- **建议**:
  - 默认只报告可修复项。
  - 增加 `--repair` 显式触发自动重分析。
  - 增加 `--dry-run` 输出将重分析的章节列表和预计成本。

### Suggestion 9: 缺少 lint/format/type check 工具链

- **位置**: `pyproject.toml`
- **问题**: 只有 pytest 配置，没有 ruff、black、mypy/pyright、pre-commit。项目已到 17k 行，靠人工风格维护会越来越贵。
- **建议**:
  - 引入 `ruff check`, `ruff format`, `pyright` 或 `mypy`。
  - 先以宽松规则落地，逐步收紧。

### Suggestion 10: `data/` 中 schema 与运行数据边界不够清晰

- **位置**: `.gitignore:36-41`, `data/schemas/`, `data/tags_view.yaml`
- **问题**: `.gitignore` 排除了部分运行数据，但 `data/` 下同时放 schema、标签视图、进度文件。长期容易误提交生成物或误删契约文件。
- **建议**:
  - `data/schemas/` 改名为 `schemas/` 或 `contracts/`。
  - 运行数据统一放 `workspace_data/` 或 `data/runtime/`，并整体 ignore。

## 外部参考对照

1. **LlamaIndex Ingestion Pipeline**  
   外部主流做法是把文档处理抽象为 transformation pipeline，并缓存中间结果。项目当前的 ingest/analyze/embed/refine 分层方向一致，但缺少统一的 pipeline artifact manifest 和可复跑配置快照。  
   参考: https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/

2. **LangChain Parent Document Retriever / 多粒度检索**  
   社区常见做法是“小块用于召回，大块用于上下文”。本项目按章节摘要向量化适合写作功能检索，但建议补充“场景片段/原文小块索引 + 章节级父文档返回”的双索引。  
   参考: https://python.langchain.com/docs/how_to/parent_document_retriever/

3. **Haystack Indexing Pipeline**  
   Haystack 强调 DocumentCleaner、DocumentSplitter、Embedder、Writer 等显式组件。项目已有类似阶段，但组件接口还不够统一，特别是搜索层和 CLI 展示层耦合。  
   参考: https://docs.haystack.deepset.ai/docs/indexing-pipelines

4. **Qdrant Hybrid Search**  
   向量检索只靠 dense embedding 容易漏掉专名、设定名、术语；Qdrant 等系统强调 dense + sparse 混合查询。小说素材尤其多专名，建议加入 BM25/pg_trgm/sparse vector 与 dense rerank。  
   参考: https://qdrant.tech/documentation/concepts/hybrid-queries/

5. **Ragas / RAG 评估**  
   Ragas 把 context precision/recall、faithfulness 等作为评估指标。虽然本项目不是问答 RAG，但可以借鉴“查询-期望上下文-评分”的评估方式，建立章节/人物/世界观检索基准。  
   参考: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/

## 建议路线图

### 第一优先级：修正确认存在的 bug

1. 修复 `word_count` 测试失败，统一统计口径。
2. 修复 `search_*` 返回契约，让 CLI 不再误报无结果。
3. 给 `nm search chapter/outline/character/world` 加 CLI 回归测试。

### 第二优先级：补检索评估与性能基准

1. 建立 golden query 数据集。
2. 增加 Recall@K/MRR/nDCG 指标脚本。
3. 做 `vector(4096)` 全表扫描性能基准。
4. 决定低维 embedding、Qdrant/Milvus，或结构过滤 + 小集合重排路线。

### 第三优先级：工程化收敛

1. 引入 ruff/format/type check/pre-commit。
2. 拆分搜索服务层与 CLI 展示层。
3. 统一 LLM 与 embedding 配置。
4. 文档路径和命令说明自动校验。

## 自动检查结果

- `python -m compileall -q src tests`: 通过。
- `python -m pytest`: 失败，1 failed / 49 passed / 1 skipped。
- 未发现 ruff/black/mypy/pre-commit 配置。

