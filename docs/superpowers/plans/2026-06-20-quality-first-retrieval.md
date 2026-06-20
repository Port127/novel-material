# 质量优先小说素材检索 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留现有 4096 维向量和“章节为最小分析单元”的前提下，把 Novel Material 补成可供外部 Agent 稳定调用、可评测、可降级、可扩展到 500～5000 本小说的质量优先检索后端。

**Architecture:** 实施分三阶段推进。阶段一先修复搜索函数与 CLI 的返回契约，建立 JSON 协议和 4096 维精确检索评测基线；阶段二增加中文词法、结构化、语义三路召回，使用 RRF、结果多样性和邻章上下文形成质量模式；阶段三增加可插拔深度重排和规模压测，只有通过质量门禁才允许启用近似候选索引。仓库只负责检索与结构化展示，外部 Agent 负责理解和生成。

**Tech Stack:** Python 3.10+、Typer、Pydantic v2、psycopg2、PostgreSQL 16、pgvector、jieba、NumPy、PyYAML、pytest。

---

## 实施前约束

- 不修改或覆盖用户当前的 `config/providers.yaml` 与 `docs/feedback.md` 工作区变更。
- 不降低现有 embedding 维度，不删除或覆盖 `*_embeddings.npz`。
- 不新增场景/事件片段数据模型，章节仍是最小分析单元。
- 不新增 `nm ask`、`nm write` 或仓库内最终内容生成功能。
- 每个阶段均可独立交付；阶段一未通过前不得执行阶段二数据库迁移。
- 所有数据库查询测试默认使用 fake connection；真实数据库测试使用 `integration` 标记，避免普通单测依赖 Docker。

## 文件结构与职责

### 新建文件

- `src/novel_material/search/models.py`：稳定的请求、结果、来源、追踪和响应模型。
- `src/novel_material/search/db.py`：只读数据库连接和数据库异常归一化。
- `src/novel_material/search/serialization.py`：JSON 与 Rich 展示共用序列化。
- `src/novel_material/search/text.py`：中文分词和可索引文本构造。
- `src/novel_material/search/fusion.py`：RRF、去重和跨素材多样性控制。
- `src/novel_material/search/context.py`：邻章摘要与原文行号补全。
- `src/novel_material/search/service.py`：三路召回、降级、时间预算和最终编排。
- `src/novel_material/search/rerank.py`：重排协议、规则重排和 LLM 重排。
- `src/novel_material/eval/search_metrics.py`：Recall、MRR、nDCG、Precision、多样性指标。
- `src/novel_material/eval/search_eval.py`：Golden Query 加载、候选导出和评测执行。
- `src/novel_material/cli/eval.py`：`nm eval search` 命令。
- `src/novel_material/storage/migrations/003_add_search_documents.sql`：词法索引字段与 GIN/pg_trgm 索引。
- `src/novel_material/storage/migrate.py`：可重复执行的迁移入口。
- `scripts/benchmark_search.py`：25 万、50 万、250 万章容量压测。
- `eval/search_queries.yaml`：真实业务查询与人工相关性标注。
- `tests/search/fakes.py`：搜索数据库测试替身。
- `tests/search/test_models.py`
- `tests/search/test_contracts.py`
- `tests/search/test_cli.py`
- `tests/search/test_text.py`
- `tests/search/test_fusion.py`
- `tests/search/test_context.py`
- `tests/search/test_service.py`
- `tests/search/test_rerank.py`
- `tests/eval/test_search_metrics.py`
- `tests/eval/test_search_eval.py`
- `tests/storage/test_search_migration.py`

### 修改文件

- `src/novel_material/search/chapter.py`、`event.py`、`outline.py`、`character.py`、`world.py`、`detail.py`、`insight.py`：只负责查询并返回结构化结果，禁止打印。
- `src/novel_material/search/__init__.py`：导出统一模型与搜索服务。
- `src/novel_material/cli/search.py`：补齐命令、参数、JSON 输出和明确退出码。
- `src/novel_material/cli/main.py`：注册 `nm eval`。
- `src/novel_material/cli/storage.py`：注册 `nm storage migrate`。
- `src/novel_material/storage/schema.sql`：新数据库直接包含词法索引结构。
- `src/novel_material/storage/sync_chapters.py`、`sync_meta.py`、`sync_outline.py`、`sync_characters.py`、`sync_worldbuilding.py`：同步 `search_tokens`。
- `src/novel_material/infra/embedding.py`、`src/novel_material/storage/embedding.py`、`src/novel_material/storage/sync_utils.py`：记录并校验 embedding provenance。
- `.agents/skills/nm-search/SKILL.md`：改用 `--json`，补齐 event/detail/insight 和降级说明。
- `docs/REQUIREMENTS.md`、`ARCHITECTURE.md`、`docs/USER_MANUAL.md`、`docs/README.md`：同步最终行为。

---

## 阶段一：可靠契约与质量基线

### Task 1：建立统一搜索数据模型

**Files:**
- Create: `src/novel_material/search/models.py`
- Modify: `src/novel_material/search/__init__.py`
- Test: `tests/search/test_models.py`

- [ ] **Step 1: 编写模型失败测试**

```python
from pydantic import ValidationError
import pytest

from novel_material.search.models import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchTrace,
    SourceLocation,
)


def test_search_request_rejects_candidate_limit_below_limit():
    with pytest.raises(ValidationError):
        SearchRequest(query="雨中告别", limit=10, candidate_limit=5)


def test_search_response_serializes_stable_agent_contract():
    result = SearchResult(
        result_id="chapter:nm_demo:7",
        document_type="chapter",
        material_id="nm_demo",
        chapter=7,
        title="第七章 告别",
        summary="主角在雨中向导师告别。",
        source=SourceLocation(chapter=7, start_line=101, end_line=160),
        scores={"semantic": 0.91},
        matched_fields=["summary"],
    )
    response = SearchResponse(
        query="雨中告别",
        results=[result],
        trace=SearchTrace(stages=["semantic"], elapsed_ms={"semantic": 12.5}),
    )
    payload = response.model_dump(mode="json")
    assert payload["results"][0]["result_id"] == "chapter:nm_demo:7"
    assert payload["trace"]["degraded"] is False
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/search/test_models.py -v`

Expected: FAIL，提示 `novel_material.search.models` 不存在。

- [ ] **Step 3: 实现 Pydantic 模型**

```python
"""Stable contracts shared by search services, CLI, eval, and agents."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

DocumentType = Literal["chapter", "event", "outline", "character", "world", "detail", "insight"]
SearchMode = Literal["quality", "exact"]


class SourceLocation(BaseModel):
    chapter: int | None = None
    start_line: int | None = None
    end_line: int | None = None


class NeighborContext(BaseModel):
    previous_summary: str | None = None
    next_summary: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    document_types: list[DocumentType] = Field(default_factory=lambda: ["chapter"])
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=100)
    candidate_limit: int = Field(default=200, ge=1, le=1000)
    mode: SearchMode = "quality"
    time_budget_seconds: int = Field(default=180, ge=1, le=180)

    @model_validator(mode="after")
    def validate_candidate_limit(self):
        if self.candidate_limit < self.limit:
            raise ValueError("candidate_limit 不能小于 limit")
        return self


class SearchResult(BaseModel):
    result_id: str
    document_type: DocumentType
    material_id: str
    chapter: int | None = None
    title: str = ""
    summary: str = ""
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: SourceLocation | None = None
    neighbors: NeighborContext | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    matched_fields: list[str] = Field(default_factory=list)
    final_score: float | None = None
    rank_reason: str = ""


class SearchTrace(BaseModel):
    stages: list[str] = Field(default_factory=list)
    candidate_counts: dict[str, int] = Field(default_factory=dict)
    elapsed_ms: dict[str, float] = Field(default_factory=dict)
    embedding_version: str | None = None
    degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    trace: SearchTrace
```

同时在 `search/__init__.py` 导出上述公共类型。

- [ ] **Step 4: 运行模型测试和全量测试**

Run: `python -m pytest tests/search/test_models.py -v && python -m pytest -q`

Expected: 模型测试 PASS；全量保持 `73 passed, 1 skipped` 或更多通过项。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/search/models.py src/novel_material/search/__init__.py tests/search/test_models.py
git commit -m "feat(search): add stable search contracts"
```

### Task 2：统一只读数据库边界与错误语义

**Files:**
- Create: `src/novel_material/search/db.py`
- Create: `tests/search/fakes.py`
- Test: `tests/search/test_contracts.py`

- [ ] **Step 1: 编写数据库边界失败测试**

```python
import pytest

from novel_material.search.db import SearchDatabaseError, readonly_connection


def test_readonly_connection_reports_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SearchDatabaseError, match="DATABASE_URL"):
        with readonly_connection(database_url=None):
            pass


def test_readonly_connection_closes_connection(monkeypatch):
    class FakeConnection:
        closed = False
        def set_session(self, **kwargs):
            assert kwargs == {"readonly": True, "autocommit": True}
        def close(self):
            self.closed = True

    fake = FakeConnection()
    monkeypatch.setattr("psycopg2.connect", lambda *_args, **_kwargs: fake)
    with readonly_connection("postgresql://test") as conn:
        assert conn is fake
    assert fake.closed is True
```

- [ ] **Step 2: 确认测试失败**

Run: `python -m pytest tests/search/test_contracts.py -v`

Expected: FAIL，提示 `search.db` 不存在。

- [ ] **Step 3: 实现连接上下文**

```python
"""Read-only PostgreSQL boundary for search."""

from contextlib import contextmanager
import os

import psycopg2


class SearchDatabaseError(RuntimeError):
    pass


@contextmanager
def readonly_connection(database_url: str | None = None):
    dsn = database_url or os.getenv("DATABASE_URL")
    if not dsn:
        raise SearchDatabaseError("DATABASE_URL 未配置")
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
        conn.set_session(readonly=True, autocommit=True)
    except psycopg2.Error as exc:
        raise SearchDatabaseError(f"数据库连接失败: {exc}") from exc
    try:
        yield conn
    finally:
        conn.close()
```

`tests/search/fakes.py` 提供记录 SQL、参数和预设行的 `FakeConnection/FakeCursor`，后续所有搜索模块测试复用，禁止每个测试重复造替身。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/search/test_contracts.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/search/db.py tests/search/fakes.py tests/search/test_contracts.py
git commit -m "refactor(search): centralize read-only database access"
```

### Task 3：修复所有搜索函数的返回契约

**Files:**
- Modify: `src/novel_material/search/chapter.py`
- Modify: `src/novel_material/search/event.py`
- Modify: `src/novel_material/search/outline.py`
- Modify: `src/novel_material/search/character.py`
- Modify: `src/novel_material/search/world.py`
- Modify: `src/novel_material/search/detail.py`
- Modify: `src/novel_material/search/insight.py`
- Test: `tests/search/test_contracts.py`

- [ ] **Step 1: 增加各类型返回模型测试**

```python
@pytest.mark.parametrize(
    ("target", "call", "expected_type"),
    [
        ("novel_material.search.chapter.readonly_connection", lambda: search_chapters("告别"), "chapter"),
        ("novel_material.search.event.readonly_connection", lambda: search_events("告别", keyword=True), "event"),
        ("novel_material.search.outline.readonly_connection", lambda: search_outlines(query="复仇"), "outline"),
        ("novel_material.search.character.readonly_connection", lambda: search_characters(query="导师"), "character"),
        ("novel_material.search.world.readonly_connection", lambda: search_worldbuilding(query="宗门"), "world"),
        ("novel_material.search.detail.readonly_connection", lambda: search_detail(query="反转"), "detail"),
    ],
)
def test_db_search_functions_return_models_without_printing(monkeypatch, capsys, target, call, expected_type):
    fake = fake_connection_with_one_row(expected_type)

    @contextmanager
    def fake_readonly_connection(*_args, **_kwargs):
        yield fake

    monkeypatch.setattr(target, fake_readonly_connection)
    results = call()
    assert len(results) == 1
    assert results[0].document_type == expected_type
    assert capsys.readouterr().out == ""
```

为 `insight` 增加独立断言：仍从 YAML 读取，但返回 `SearchResult(document_type="insight")`。

- [ ] **Step 2: 运行测试确认旧实现失败**

Run: `python -m pytest tests/search/test_contracts.py -v`

Expected: FAIL；旧函数返回 `None` 或 `dict`，并向 stdout 打印。

- [ ] **Step 3: 重构查询函数**

每个模块执行同一规则：

1. 删除 `click` 装饰器和模块内 `main()`；正式入口只保留 Typer CLI。
2. 使用 `readonly_connection()`。
3. 使用 `with conn.cursor(cursor_factory=RealDictCursor)`。
4. 将 `fetchall()` 映射成 `SearchResult`。
5. 无结果返回空列表；数据库错误向上传递；禁止打印。

章节映射必须包含：

```python
SearchResult(
    result_id=f"chapter:{row['material_id']}:{row['chapter']}",
    document_type="chapter",
    material_id=row["material_id"],
    chapter=row["chapter"],
    title=row.get("title") or "",
    summary=row.get("summary") or "",
    metadata={
        "novel_name": row.get("novel_name"),
        "genre": row.get("genre") or [],
        "tension_level": row.get("tension_level"),
        "pacing": row.get("pacing"),
        "chapter_functions": row.get("chapter_functions") or [],
        "characters_appear": row.get("characters_appear") or [],
        "key_event": row.get("key_event"),
        "key_plot_point": row.get("key_plot_point"),
    },
    scores={"semantic": float(1 - row["distance"])} if row.get("distance") is not None else {},
    matched_fields=["summary"] if row.get("distance") is not None else [],
)
```

其他类型使用稳定 ID：`event:{material}:{chapter}`、`outline:{material}`、`character:{material}:{name}`、`world:{material}:{entity_type}:{name}`、`detail:{material}:{act}:{sequence}`、`insight:{material}:{chapter}`。

- [ ] **Step 4: 运行契约测试与既有 insight 测试**

Run: `python -m pytest tests/search/test_contracts.py tests/search/test_insight_search.py -v`

Expected: PASS。若既有 insight 测试仍断言 dict，改为 `results[0].model_dump()` 后比较相同字段。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/search tests/search/test_contracts.py tests/search/test_insight_search.py
git commit -m "fix(search): return structured results from all search modules"
```

### Task 4：补齐 CLI、JSON 输出和明确退出码

**Files:**
- Create: `src/novel_material/search/serialization.py`
- Modify: `src/novel_material/cli/search.py`
- Test: `tests/search/test_cli.py`

- [ ] **Step 1: 编写 CLI 失败测试**

```python
import json
from typer.testing import CliRunner

from novel_material.cli.main import app
from novel_material.search.models import SearchResult

runner = CliRunner()


def test_chapter_json_is_machine_readable(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.search.search_chapters",
        lambda **_kwargs: [SearchResult(
            result_id="chapter:nm_demo:1",
            document_type="chapter",
            material_id="nm_demo",
            chapter=1,
            title="开篇",
            summary="主角陷入困境。",
        )],
    )
    result = runner.invoke(app, ["search", "chapter", "开局困境", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["results"][0]["result_id"] == "chapter:nm_demo:1"


def test_search_help_exposes_event_detail_and_insight():
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0
    assert all(name in result.stdout for name in ("event", "detail", "insight"))


def test_database_failure_exits_nonzero(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.search.search_chapters",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("数据库连接失败")),
    )
    result = runner.invoke(app, ["search", "chapter", "开局困境"])
    assert result.exit_code == 1
    assert "数据库连接失败" in result.stdout
    assert "未找到" not in result.stdout
```

- [ ] **Step 2: 确认测试失败**

Run: `python -m pytest tests/search/test_cli.py -v`

Expected: FAIL；当前没有 `--json`、event/detail 命令和正确异常退出。

- [ ] **Step 3: 实现共用序列化**

```python
import json

from novel_material.search.models import SearchResponse, SearchResult, SearchTrace


def build_response(query: str, results: list[SearchResult]) -> SearchResponse:
    return SearchResponse(query=query, results=results, trace=SearchTrace(stages=["legacy"]))


def response_json(response: SearchResponse) -> str:
    return json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 重写 Typer 命令参数**

所有命令增加 `--json`。`chapter/outline/character/world` 增加 `--semantic` 和现有底层过滤参数；注册 `event` 与 `detail`；保留 `insight`。命令调用放在统一 `try/except` 中，异常时输出红色诊断并 `raise typer.Exit(1)`；空列表才输出“未找到”。JSON 模式不得输出进度提示或 Rich 表格。

- [ ] **Step 5: 运行 CLI 测试和真实帮助检查**

Run: `python -m pytest tests/search/test_cli.py -v && nm search --help`

Expected: 测试 PASS；帮助中包含 7 类搜索命令。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/cli/search.py src/novel_material/search/serialization.py tests/search/test_cli.py
git commit -m "feat(search): expose complete JSON search CLI"
```

### Task 5：实现检索评测指标

**Files:**
- Create: `src/novel_material/eval/search_metrics.py`
- Modify: `src/novel_material/eval/__init__.py`
- Test: `tests/eval/test_search_metrics.py`

- [ ] **Step 1: 编写确定性指标测试**

```python
from novel_material.eval.search_metrics import evaluate_ranking


def test_evaluate_ranking_computes_recall_mrr_ndcg_precision_and_diversity():
    ranked = ["a", "b", "c", "d"]
    judgments = {"a": 3, "c": 2, "x": 1}
    material_ids = {"a": "n1", "b": "n1", "c": "n2", "d": "n3"}
    metrics = evaluate_ranking(ranked, judgments, material_ids, k=4)
    assert metrics["recall@4"] == 2 / 3
    assert metrics["mrr"] == 1.0
    assert metrics["precision@4"] == 0.5
    assert 0 < metrics["ndcg@4"] <= 1
    assert metrics["distinct_materials@4"] == 3
```

- [ ] **Step 2: 确认测试失败**

Run: `python -m pytest tests/eval/test_search_metrics.py -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现纯函数指标**

实现 `recall_at_k`、`reciprocal_rank`、`precision_at_k`、`ndcg_at_k` 和 `evaluate_ranking`。相关性大于 0 视为相关；nDCG 使用 `gain = 2**relevance - 1` 和 `log2(rank + 1)`；所有空集合返回 0.0，不抛除零异常。

- [ ] **Step 4: 运行指标测试**

Run: `python -m pytest tests/eval/test_search_metrics.py -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/eval tests/eval/test_search_metrics.py
git commit -m "feat(eval): add deterministic search ranking metrics"
```

### Task 6：建立 Golden Query 标注与基线命令

**Files:**
- Create: `eval/search_queries.yaml`
- Create: `src/novel_material/eval/search_eval.py`
- Create: `src/novel_material/cli/eval.py`
- Modify: `src/novel_material/cli/main.py`
- Test: `tests/eval/test_search_eval.py`

- [ ] **Step 1: 编写数据集校验失败测试**

```python
import pytest

from novel_material.eval.search_eval import load_search_cases, validate_labeled_cases


def test_validate_labeled_cases_rejects_missing_judgments(tmp_path):
    path = tmp_path / "queries.yaml"
    path.write_text(
        "- id: chapter_001\n  query: 开局困境\n  document_type: chapter\n  judgments: {}\n",
        encoding="utf-8",
    )
    cases = load_search_cases(path)
    with pytest.raises(ValueError, match="chapter_001"):
        validate_labeled_cases(cases)
```

- [ ] **Step 2: 实现数据集加载、候选导出和评分**

`search_eval.py` 定义以下公开接口：

```python
@dataclass(frozen=True)
class SearchEvalCase:
    id: str
    query: str
    document_type: str
    filters: dict
    judgments: dict[str, int]
    require_diversity: bool
    require_neighbors: bool


```

- `load_search_cases(path: Path) -> list[SearchEvalCase]`：解析 YAML，缺少必填字段时报告 case id 和字段名。
- `validate_labeled_cases(cases: list[SearchEvalCase]) -> None`：逐项确认 judgments 非空且相关性只能为 0、1、2、3。
- `export_candidates(cases, search_callable, output_path: Path, limit: int = 30) -> None`：执行检索并写出待人工标注候选，不修改输入文件。
- `evaluate_cases(cases, search_callable) -> dict`：返回逐查询指标、按 document type 聚合指标和总体宏平均。

候选导出 YAML 必须包含 `case_id/query/result_id/material_id/title/summary/relevance`，其中 `relevance` 初始为 `null`；评分命令遇到 `null` 或空 judgments 必须拒绝执行，防止伪造质量分数。

- [ ] **Step 3: 注册评测 CLI**

提供：

```bash
nm eval search prepare --queries eval/search_queries.yaml --output eval/search_candidates.yaml
nm eval search score --queries eval/search_queries.yaml --output eval/search_report.json
```

`prepare` 只生成候选；用户人工填写 0～3 分后，通过独立 `import-labels` 子命令把评分合并回 `search_queries.yaml`。`score` 输出逐查询指标和总体宏平均，禁止只输出平均值。

- [ ] **Step 4: 写入首批真实查询种子**

`eval/search_queries.yaml` 固定包含 30 条：章纲 10、事件 10、人物 3、大纲 3、世界观 3、细纲 1。查询直接取自 `docs/REQUIREMENTS.md`，包括“开局困境”“雨中告别”“导师型人物”“废柴逆袭大纲”“修仙力量体系”“感情线节拍”。初始文件明确标记 `status: awaiting_human_labels`，不得放置猜测的相关 ID。

- [ ] **Step 5: 运行测试并导出当前候选**

Run: `python -m pytest tests/eval/test_search_eval.py -v`

Expected: PASS。

Run: `nm eval search prepare --queries eval/search_queries.yaml --output eval/search_candidates.yaml`

Expected: 生成 30 个 case 的候选；数据库不可用时非零退出且不修改原查询文件。

- [ ] **Step 6: 完成人工标注质量门槛**

逐条阅读候选摘要与必要的原文章节，填写 0（不相关）到 3（高度相关）。每个 case 至少标注 10 个候选，其中至少包含 3 个困难负例。完成后执行 `import-labels`，确认 `validate_labeled_cases` 通过。

- [ ] **Step 7: 保存 4096 维精确检索基线**

Run: `nm eval search score --queries eval/search_queries.yaml --mode exact --output eval/baselines/4096-exact.json`

Expected: 报告包含 30 条逐查询结果、Recall@50、Recall@100、MRR、nDCG@10、Precision@10、多样性和耗时；此文件是后续质量门禁基线。

- [ ] **Step 8: 提交**

```bash
git add eval/search_queries.yaml eval/baselines/4096-exact.json src/novel_material/eval/search_eval.py src/novel_material/cli/eval.py src/novel_material/cli/main.py tests/eval/test_search_eval.py
git commit -m "feat(eval): establish golden search baseline"
```

## 阶段二：质量优先混合检索

### Task 7：增加 embedding provenance 与维度校验

**Files:**
- Create: `src/novel_material/storage/embedding_manifest.py`
- Modify: `src/novel_material/infra/embedding.py`
- Modify: `src/novel_material/storage/embedding.py`
- Modify: `src/novel_material/storage/sync_utils.py`
- Test: `tests/storage/test_embedding_manifest.py`

- [ ] **Step 1: 编写维度不一致失败测试**

```python
import pytest

from novel_material.storage.embedding_manifest import EmbeddingManifest, validate_vector


def test_validate_vector_rejects_wrong_dimension():
    manifest = EmbeddingManifest(
        provider="ollama",
        model="qwen3-embedding",
        dimension=4096,
        text_version="chapter-summary-v1",
    )
    with pytest.raises(ValueError, match="期望 4096.*实际 3"):
        validate_vector([0.1, 0.2, 0.3], manifest)
```

- [ ] **Step 2: 实现 manifest**

manifest 字段固定为 `provider/model/dimension/text_version/created_at`。每个 NPZ 同目录保存同名 `.manifest.yaml`，例如 `chapter_embeddings.manifest.yaml`。旧 NPZ 没有 manifest 时读取成功，但同步日志必须标记 `legacy-unverified`；不得因此自动重建向量。

- [ ] **Step 3: 在生成和同步边界校验**

`get_embedding()` 返回后立即校验配置维度；所有 `_save_*embeddings` 保存 manifest；`_load_embeddings_npz` 可选返回 manifest。数据库同步遇到维度不一致时中止该素材同步，不能把错误向量静默写入 PostgreSQL。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/storage/test_embedding_manifest.py -v`

Expected: PASS；不访问真实 embedding API。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/infra/embedding.py src/novel_material/storage tests/storage/test_embedding_manifest.py
git commit -m "feat(embedding): record and validate embedding provenance"
```

### Task 8：建立中文词法索引迁移

**Files:**
- Create: `src/novel_material/search/text.py`
- Create: `src/novel_material/storage/migrations/003_add_search_documents.sql`
- Create: `src/novel_material/storage/migrate.py`
- Modify: `src/novel_material/storage/schema.sql`
- Modify: `src/novel_material/cli/storage.py`
- Test: `tests/search/test_text.py`
- Test: `tests/storage/test_search_migration.py`

- [ ] **Step 1: 编写中文分词失败测试**

```python
from novel_material.search.text import build_search_text, tokenize_for_search


def test_tokenize_for_search_keeps_phrase_and_chinese_terms():
    tokens = tokenize_for_search("主角在雨中告别导师")
    assert "雨中" in tokens
    assert "告别" in tokens
    assert "导师" in tokens


def test_build_search_text_ignores_empty_values_and_flattens_lists():
    text = build_search_text("第七章", None, ["雨夜", "告别"], {"hook": "悬念"})
    assert "第七章" in text
    assert "雨夜" in text
    assert "悬念" in text
```

- [ ] **Step 2: 实现确定性中文文本构造**

`build_search_text(*parts)` 按参数顺序递归展开字符串、列表和字典值；`tokenize_for_search(text)` 使用 `jieba.cut(..., cut_all=False)`，去除纯空白但保留单字专名，同时把原始完整短语放在首位。输出为空格分隔字符串，保证 PostgreSQL `simple` 配置能够索引。

- [ ] **Step 3: 编写 SQL 迁移**

`003_add_search_documents.sql` 必须幂等：

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE chapters ADD COLUMN IF NOT EXISTS search_tokens TEXT NOT NULL DEFAULT '';
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS search_document tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', search_tokens)) STORED;
CREATE INDEX IF NOT EXISTS idx_chapters_search_document ON chapters USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_chapters_title_trgm ON chapters USING GIN(title gin_trgm_ops);
```

迁移中逐表执行以下明确变更，全部使用 `IF NOT EXISTS`：

- `novels`：增加 `search_tokens/search_document`、`idx_novels_search_document`，并为 `name` 增加 `idx_novels_name_trgm`。
- `characters`：增加 `search_tokens/search_document`、`idx_characters_search_document`，并为 `name` 增加 `idx_characters_name_trgm`。
- `worldbuilding_entities`：增加 `search_tokens/search_document`、`idx_worldbuilding_search_document`，并为 `name` 增加 `idx_worldbuilding_name_trgm`。
- `outline_sequences`：增加 `search_tokens/search_document`、`idx_outline_sequences_search_document`，并为 `title` 增加 `idx_outline_sequences_title_trgm`。
- `outline_beats`：增加 `search_tokens/search_document`、`idx_outline_beats_search_document`，并为 `title` 增加 `idx_outline_beats_title_trgm`。

每个 `search_document` 都使用 `GENERATED ALWAYS AS (to_tsvector('simple', search_tokens)) STORED`，检索文档索引使用 GIN，名称/标题模糊匹配索引使用 `gin_trgm_ops`。迁移不得修改或删除任何 4096 维向量列。

- [ ] **Step 4: 实现迁移运行器**

创建 `schema_migrations(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ)`；按文件名前缀排序执行 `.sql`；单个迁移事务失败必须回滚并非零退出。注册：

```bash
nm storage migrate
```

- [ ] **Step 5: 同步新数据库 schema**

把 003 的最终列和索引同步写入 `schema.sql`，保证新数据库执行 `nm storage init-db` 后无需再补迁移。

- [ ] **Step 6: 运行单测和临时数据库集成测试**

Run: `python -m pytest tests/search/test_text.py tests/storage/test_search_migration.py -v`

Expected: PASS。

Run: `nm storage migrate`

Expected: 首次应用 003；再次运行显示“无待执行迁移”，表结构不重复。

- [ ] **Step 7: 提交**

```bash
git add src/novel_material/search/text.py src/novel_material/storage/migrations/003_add_search_documents.sql src/novel_material/storage/migrate.py src/novel_material/storage/schema.sql src/novel_material/cli/storage.py tests/search/test_text.py tests/storage/test_search_migration.py
git commit -m "feat(search): add Chinese lexical search indexes"
```

### Task 9：在同步阶段回填词法检索文本

**Files:**
- Modify: `src/novel_material/storage/sync_chapters.py`
- Modify: `src/novel_material/storage/sync_meta.py`
- Modify: `src/novel_material/storage/sync_outline.py`
- Modify: `src/novel_material/storage/sync_characters.py`
- Modify: `src/novel_material/storage/sync_worldbuilding.py`
- Test: `tests/storage/test_search_tokens_sync.py`

- [ ] **Step 1: 编写章节搜索文本测试**

```python
from novel_material.storage.sync_chapters import build_chapter_search_tokens


def test_build_chapter_search_tokens_uses_all_retrieval_fields():
    tokens = build_chapter_search_tokens({
        "title": "雨夜告别",
        "summary": "主角向导师辞行。",
        "key_event": "师徒分别",
        "plot_progress": "主角独自上路",
        "chapter_functions": ["关系转折"],
        "emotional_tone": ["悲伤"],
        "scene_type": ["雨夜"],
        "technique": ["环境烘托"],
        "hook_type": "新旅程",
    })
    for term in ("导师", "分别", "关系", "悲伤", "雨夜", "环境", "旅程"):
        assert term in tokens
```

- [ ] **Step 2: 为每类实体定义唯一文本构造函数**

- Chapter：标题、摘要、关键事件、情节推进、功能、情绪、场景、技法、钩子。
- Novel：名称、前提、题材、主题、基调、结构类型、标签。
- Character：姓名、原型、角色、弧线、叙事功能、描述、心理字段。
- World：名称、实体类型、描述、properties。
- Outline sequence/beat：标题、描述、幕、序列、节拍。

函数都调用 `build_search_text/tokenize_for_search`，不复制分词逻辑。

- [ ] **Step 3: 修改 INSERT/UPDATE SQL**

每个同步模块在原事务中写入 `search_tokens`，`ON CONFLICT DO UPDATE` 同步更新。缺失向量不影响词法文本写入。

- [ ] **Step 4: 回填现有数据**

Run: `nm storage sync-all`

Expected: 现有已通过 schema 校验的素材写入 `search_tokens`；缺向量素材仍有非空词法索引；失败素材按现有规则报告而不触发无关重分析。

- [ ] **Step 5: 验证数据库覆盖率**

Run: `SELECT count(*) FILTER (WHERE search_tokens <> ''), count(*) FROM chapters;`

Expected: 可同步章节的非空覆盖率为 100%。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/storage/sync_*.py tests/storage/test_search_tokens_sync.py
git commit -m "feat(storage): populate lexical search documents"
```

### Task 10：实现 RRF 融合与跨素材多样性

**Files:**
- Create: `src/novel_material/search/fusion.py`
- Test: `tests/search/test_fusion.py`

- [ ] **Step 1: 编写融合与多样性失败测试**

```python
from novel_material.search.fusion import diversify_results, reciprocal_rank_fusion
from novel_material.search.models import SearchResult


def item(result_id, material_id):
    return SearchResult(
        result_id=result_id,
        document_type="chapter",
        material_id=material_id,
    )


def test_rrf_rewards_results_found_by_multiple_retrievers():
    a, b, c = item("a", "n1"), item("b", "n2"), item("c", "n3")
    fused = reciprocal_rank_fusion({"lexical": [a, b], "semantic": [c, a]}, k=60)
    assert fused[0].result_id == "a"
    assert set(fused[0].scores) >= {"lexical_rrf", "semantic_rrf"}


def test_diversity_caps_single_material_without_dropping_limit():
    results = [item(f"a{i}", "n1") for i in range(5)] + [item("b", "n2"), item("c", "n3")]
    diverse = diversify_results(results, limit=5, per_material_limit=2)
    assert sum(r.material_id == "n1" for r in diverse) == 2
    assert len(diverse) == 5
```

- [ ] **Step 2: 实现融合**

RRF 公式固定为 `1 / (k + rank)`，rank 从 1 开始。相同 `result_id` 合并 metadata、matched_fields 和 scores；最终按 RRF 总分降序，稳定次序使用 `result_id`。

- [ ] **Step 3: 实现多样性控制**

第一轮按 `per_material_limit` 选取；不足 `limit` 时第二轮从被跳过结果补齐。指定 `filters.material_id` 时关闭限制。

- [ ] **Step 4: 运行测试并提交**

Run: `python -m pytest tests/search/test_fusion.py -v`

Expected: PASS。

```bash
git add src/novel_material/search/fusion.py tests/search/test_fusion.py
git commit -m "feat(search): add RRF fusion and result diversity"
```

### Task 11：补全邻章上下文与原文定位

**Files:**
- Create: `src/novel_material/search/context.py`
- Test: `tests/search/test_context.py`

- [ ] **Step 1: 编写上下文失败测试**

```python
from novel_material.search.context import enrich_chapter_result
from novel_material.search.models import SearchResult


def test_enrich_chapter_result_adds_neighbors_and_line_range(tmp_path):
    novel_dir = tmp_path / "nm_demo"
    novel_dir.mkdir()
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 2\n  title: 第二章\n  start_line: 21\n  end_line: 40\n",
        encoding="utf-8",
    )
    result = SearchResult(
        result_id="chapter:nm_demo:2",
        document_type="chapter",
        material_id="nm_demo",
        chapter=2,
    )
    enriched = enrich_chapter_result(
        result,
        summaries={1: "前章", 2: "本章", 3: "后章"},
        novels_dir=tmp_path,
    )
    assert enriched.neighbors.previous_summary == "前章"
    assert enriched.neighbors.next_summary == "后章"
    assert enriched.source.start_line == 21
    assert enriched.source.end_line == 40
```

- [ ] **Step 2: 实现上下文补全**

仅对 chapter/event/insight 结果补全。批量按 `(material_id, chapter)` 查询前后摘要，避免 N+1 数据库查询；再按 material 缓存 `chapter_index.yaml`。第一章/末章缺邻居是合法边界，其他缺失写入 trace 降级原因。

- [ ] **Step 3: 运行测试并提交**

Run: `python -m pytest tests/search/test_context.py -v`

Expected: PASS。

```bash
git add src/novel_material/search/context.py tests/search/test_context.py
git commit -m "feat(search): attach neighbor context and source locations"
```

### Task 12：实现三路召回与质量模式编排

**Files:**
- Create: `src/novel_material/search/service.py`
- Modify: `src/novel_material/search/chapter.py`
- Modify: `src/novel_material/search/event.py`
- Modify: `src/novel_material/search/outline.py`
- Modify: `src/novel_material/search/character.py`
- Modify: `src/novel_material/search/world.py`
- Modify: `src/novel_material/search/detail.py`
- Test: `tests/search/test_service.py`

- [ ] **Step 1: 编写质量模式与降级失败测试**

```python
from novel_material.search.models import SearchRequest, SearchResult
from novel_material.search.service import SearchService


def result(result_id, material_id):
    return SearchResult(
        result_id=result_id,
        document_type="chapter",
        material_id=material_id,
    )


def test_quality_mode_runs_three_retrievers_and_fuses_results():
    service = SearchService(
        lexical=lambda _request: [result("a", "n1")],
        semantic=lambda _request: [result("b", "n2"), result("a", "n1")],
        structured=lambda _request: [result("c", "n3")],
    )
    response = service.search(SearchRequest(query="雨中告别", limit=3))
    assert response.results[0].result_id == "a"
    assert response.trace.candidate_counts == {"lexical": 1, "semantic": 2, "structured": 1}


def test_embedding_failure_degrades_to_lexical_and_structured():
    def fail(_request):
        raise RuntimeError("embedding unavailable")

    service = SearchService(
        lexical=lambda _request: [result("a", "n1")],
        semantic=fail,
        structured=lambda _request: [result("b", "n2")],
    )
    response = service.search(SearchRequest(query="宗门", limit=2))
    assert [r.result_id for r in response.results] == ["a", "b"]
    assert response.trace.degraded is True
    assert any("semantic" in reason for reason in response.trace.degradation_reasons)
```

- [ ] **Step 2: 拆出各类型召回函数**

每个 DB 搜索模块提供三类同签名函数：`retrieve_<type>_lexical(request: SearchRequest) -> list[SearchResult]`、`retrieve_<type>_semantic(request: SearchRequest) -> list[SearchResult]`、`retrieve_<type>_structured(request: SearchRequest) -> list[SearchResult]`。其中 `<type>` 分别替换为 `chapters`、`events`、`outlines`、`characters`、`worldbuilding` 和 `details`；`insight` 保持 YAML 召回，不创建不存在的数据库表。

词法 SQL 使用 `search_document @@ plainto_tsquery('simple', %s)` 并按 `ts_rank_cd` 排序，同时对名称列保留 trigram/精确匹配。语义 SQL继续使用完整 4096 维 `<=>` 精确排序。结构召回只在 request filters 非空时执行，使用现有数组、JSONB 和标量索引。

- [ ] **Step 3: 实现 SearchService**

`SearchService.search()`：

1. 按 document type 路由召回器；
2. 记录 `perf_counter()` 阶段耗时；
3. 单路失败只记录降级，三路全部失败才抛异常；
4. 使用 RRF 合并；
5. 使用多样性控制；
6. 补充上下文；
7. 达到 `time_budget_seconds` 时跳过剩余阶段并返回当前最佳结果；
8. 构造 `SearchResponse`。

`mode="exact"` 固定执行现有 4096 维精确语义召回，用于基线；`mode="quality"` 执行三路召回。

- [ ] **Step 4: CLI 改用 SearchService**

所有命令统一构造 `SearchRequest`；旧 `search_*` 公共函数保留一版兼容包装，内部委托对应 retriever，避免突然破坏其他导入方。

- [ ] **Step 5: 运行服务测试与基线回归**

Run: `python -m pytest tests/search/test_service.py tests/search -v`

Expected: PASS。

Run: `nm eval search score --queries eval/search_queries.yaml --mode quality --output eval/baselines/hybrid-v1.json`

Expected: 章纲/事件 Precision@10 不低于 0.80；最终 nDCG@10 不低于 `4096-exact.json`；未达到则调整候选构造或 RRF 参数，不进入 Task 13。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/search src/novel_material/cli/search.py tests/search/test_service.py eval/baselines/hybrid-v1.json
git commit -m "feat(search): add quality-first hybrid retrieval service"
```

## 阶段三：深度重排与规模验证

### Task 13：实现可插拔深度重排与安全回退

**Files:**
- Create: `src/novel_material/search/rerank.py`
- Create: `src/novel_material/prompts/rerank.yaml`
- Modify: `src/novel_material/search/service.py`
- Modify: `config/settings.yaml`
- Test: `tests/search/test_rerank.py`

- [ ] **Step 1: 编写重排和回退失败测试**

```python
from novel_material.search.models import SearchResult
from novel_material.search.rerank import LLMReranker, RerankError


def test_llm_reranker_uses_returned_scores_and_reasons():
    candidates = [chapter("a"), chapter("b")]
    reranker = LLMReranker(call=lambda *_args, **_kwargs: {
        "rankings": [
            {"result_id": "b", "score": 0.95, "reason": "情境和情绪都匹配"},
            {"result_id": "a", "score": 0.60, "reason": "只有事件相似"},
        ]
    })
    ranked = reranker.rerank("雨中告别", candidates, time_budget_seconds=30)
    assert [r.result_id for r in ranked] == ["b", "a"]
    assert ranked[0].rank_reason == "情境和情绪都匹配"


def test_invalid_llm_output_raises_rerank_error():
    reranker = LLMReranker(call=lambda *_args, **_kwargs: {"rankings": []})
    with pytest.raises(RerankError):
        reranker.rerank("雨中告别", [chapter("a")], time_budget_seconds=30)
```

- [ ] **Step 2: 编写严格 JSON 重排 Prompt**

`rerank.yaml` 要求模型只评价候选与查询的相关性、可参考价值和互补性，不生成小说内容。输入包含 `result_id/title/summary/key_event/plot_progress/functions/emotion/scene/technique/neighbors`；输出：

```json
{"rankings":[{"result_id":"chapter:nm_x:7","score":0.0,"reason":"不超过50字"}]}
```

score 范围 0～1；必须覆盖全部输入 ID；未知或重复 ID 视为无效输出。

- [ ] **Step 3: 实现重排协议**

定义 `Reranker` Protocol 和 `IdentityReranker/LLMReranker`。LLM 以每批最多 20 条调用现有 `call_llm()`，合并批次后按 score 排序。剩余时间小于配置的最小预算时不发起新批次。

- [ ] **Step 4: 接入降级**

配置新增：

```yaml
SEARCH_RERANKER: "llm"
SEARCH_RERANK_BATCH_SIZE: 20
SEARCH_RERANK_CANDIDATES: 60
SEARCH_TIME_BUDGET_SECONDS: 180
SEARCH_PER_MATERIAL_LIMIT: 3
```

LLM 超时、JSON 错误或 API 错误时，SearchService 返回融合排序，并在 trace 写 `rerank_failed`；不得返回空列表。

- [ ] **Step 5: 运行测试与质量对比**

Run: `python -m pytest tests/search/test_rerank.py tests/search/test_service.py -v`

Expected: PASS。

Run: `nm eval search score --queries eval/search_queries.yaml --mode quality --reranker llm --output eval/baselines/rerank-v1.json`

Expected: nDCG@10 高于或等于 hybrid-v1；逐查询报告中不能有未解释的明显退化。若整体无提升，默认关闭 LLM reranker，但保留接口与实验报告。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/search/rerank.py src/novel_material/search/service.py src/novel_material/prompts/rerank.yaml config/settings.yaml tests/search/test_rerank.py eval/baselines/rerank-v1.json
git commit -m "feat(search): add deep reranking with safe fallback"
```

### Task 14：建立容量压测与近似候选质量门禁

**Files:**
- Create: `scripts/benchmark_search.py`
- Create: `tests/search/test_benchmark_gate.py`
- Create: `docs/search-benchmark.md`

- [ ] **Step 1: 编写质量门禁测试**

```python
from scripts.benchmark_search import candidate_gate


def test_candidate_gate_requires_recall_and_ndcg_thresholds():
    assert candidate_gate(candidate_recall=0.985, exact_ndcg=0.82, candidate_ndcg=0.815) is True
    assert candidate_gate(candidate_recall=0.97, exact_ndcg=0.82, candidate_ndcg=0.82) is False
    assert candidate_gate(candidate_recall=0.99, exact_ndcg=0.82, candidate_ndcg=0.80) is False
```

- [ ] **Step 2: 实现压测脚本**

命令：

```bash
python scripts/benchmark_search.py --rows 250000 --queries eval/search_queries.yaml --mode exact
python scripts/benchmark_search.py --rows 500000 --queries eval/search_queries.yaml --mode exact
python scripts/benchmark_search.py --rows 2500000 --queries eval/search_queries.yaml --mode exact
```

脚本使用独立 `search_benchmark` schema，复制/循环现有向量和元数据构造代表性规模，不写生产表；运行前打印预计磁盘占用并要求 `--confirm-large` 才允许 250 万行。输出 P50/P95、峰值内存、数据库 buffers、吞吐、逐查询结果和硬件信息。

- [ ] **Step 3: 实现可选候选实验**

实验模式只在 benchmark schema 建立 pgvector 官方支持的二值量化或子向量候选索引；取至少 1000 条候选后，用原 `vector(4096)` 精确重排。不得修改 `storage/schema.sql` 或生产迁移。

- [ ] **Step 4: 固化门禁**

`candidate_gate()` 固定要求：

- Candidate Recall ≥ 0.98；
- 最终 nDCG@10 相对精确基线下降 ≤ 0.01；
- 质量模式 P95 ≤ 180 秒；
- 30 条 Golden Query 中不得有单条从“合格”降为“无相关结果”。

- [ ] **Step 5: 在三个目标规模执行并记录结论**

将机器规格、命令、结果和是否通过门禁写入 `docs/search-benchmark.md`。只有精确模式超过 180 秒且候选模式通过全部门禁时，才能另开设计决定生产 ANN；否则继续保留精确 4096 维方案。

- [ ] **Step 6: 运行单测并提交**

Run: `python -m pytest tests/search/test_benchmark_gate.py -v`

Expected: PASS。

```bash
git add scripts/benchmark_search.py tests/search/test_benchmark_gate.py docs/search-benchmark.md
git commit -m "perf(search): add scale benchmark and quality gate"
```

### Task 15：更新 Agent Skill 和项目文档

**Files:**
- Modify: `.agents/skills/nm-search/SKILL.md`
- Modify: `docs/REQUIREMENTS.md`
- Modify: `ARCHITECTURE.md`
- Modify: `docs/USER_MANUAL.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: 更新 nm-search Skill**

明确 Agent 默认使用 `--json --mode quality`；列出 chapter/event/outline/character/world/detail/insight；说明 trace 中的降级原因；禁止 Agent 把检索结果描述成事实答案；生成仍由外部 Agent 负责。

- [ ] **Step 2: 更新架构与使用手册**

文档必须覆盖：

- 仓库是 Agentic RAG 的检索与上下文供应层，不是内部生成应用；
- 三路召回、RRF、重排、邻章和来源定位数据流；
- `--json/--mode/--candidate-limit/--time-budget` 参数；
- `nm eval search` 标注与评分流程；
- `nm storage migrate`；
- embedding 或 reranker 失败时的降级语义；
- 4096 维保留和候选索引门禁。

- [ ] **Step 3: 校验文档命令**

Run: `nm search --help && nm eval --help && nm storage --help`

Expected: 文档列出的命令都真实存在。

- [ ] **Step 4: 提交**

```bash
git add .agents/skills/nm-search/SKILL.md docs/REQUIREMENTS.md ARCHITECTURE.md docs/USER_MANUAL.md docs/README.md AGENTS.md
git commit -m "docs(search): document quality-first Agent retrieval"
```

### Task 16：最终质量与回归验收

**Files:**
- Modify only if verification reveals a scoped defect in files from Tasks 1–15.

- [ ] **Step 1: 运行完整单元测试**

Run: `python -m pytest -q`

Expected: 全部通过，保留原有唯一明确 skip 或更少；不得低于当前 `73 passed, 1 skipped` 基线。

- [ ] **Step 2: 运行搜索专项测试**

Run: `python -m pytest tests/search tests/eval tests/storage/test_search_migration.py tests/storage/test_search_tokens_sync.py -v`

Expected: 全部通过。

- [ ] **Step 3: 运行真实 CLI 冒烟测试**

```bash
nm search chapter "开局困境" --mode quality --limit 10 --json
nm search event "雨中告别" --mode quality --limit 10 --json
nm search character --archetype 导师 --mode quality --json
nm search world "宗门" --dimension faction --mode quality --json
nm search detail "高潮前铺垫" --mode quality --json
nm search insight "主角被压制后反杀" --json
```

Expected: 每条 stdout 都是合法 JSON；有结果时包含 `result_id/material_id/trace`；错误时非零退出且不得误报“未找到”。

- [ ] **Step 4: 运行最终质量报告**

Run: `nm eval search score --queries eval/search_queries.yaml --mode quality --output eval/baselines/final.json`

Expected:

- 章纲和事件 Precision@10 ≥ 0.80；
- 大纲和人物 Precision@10 ≥ 0.70；
- 世界观 Precision@10 ≥ 0.60；
- 最终 nDCG@10 不低于 4096 精确基线；
- 候选充足时 Top 10 至少 5 个不同素材；
- 原文定位覆盖率 100%；
- 非首末章邻章摘要覆盖率 100%；
- 总 P95 ≤ 180 秒。

- [ ] **Step 5: 检查工作区边界**

Run: `git status --short && git diff -- config/providers.yaml docs/feedback.md`

Expected: 用户原有两处修改仍在且内容未被本计划覆盖；无意外运行产物进入暂存区。

- [ ] **Step 6: 最终提交**

```bash
git add eval/baselines/final.json
git commit -m "test(search): record final retrieval quality baseline"
```

---

## 阶段检查点

### 阶段一完成条件

- 搜索模块不打印，只返回结构化模型。
- 7 类搜索命令可用，`--json` 稳定。
- 数据库故障与空结果语义分离。
- 30 条 Golden Query 完成人工标注。
- 保存当前 4096 维精确检索基线。

### 阶段二完成条件

- 现有向量维度和文件保持不变。
- 中文词法索引可从 YAML/DB 重建。
- 词法、结构化、4096 精确语义三路召回可独立降级。
- 混合质量不低于精确基线。
- 结果具备多样性、邻章和原文定位。

### 阶段三完成条件

- 深度重排失败不会导致检索失败。
- 完成 25 万、50 万、250 万章容量报告。
- 近似候选只在质量门禁通过后进入另一个生产设计，不在本计划中直接启用。
- 所有业务质量、完整性和 180 秒响应指标通过。

## 明确排除的后续工作

- 本计划不创建问答或写作生成命令。
- 本计划不直接迁移 Qdrant/Milvus。
- 本计划不降低到 1024/1536/2000 维。
- 本计划不删除 4096 维精确基线。
- 本计划不把 chapter_insights 拆成场景或事件片段。
