# Golden Query 候选补足 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当严格过滤的 Golden Query 少于 10 个候选时，依次用移除过滤条件的同查询结果以及 `detail` 无关键词库存补足人工标注池，同时保持精确评分语义不变。

**Architecture:** `search_eval.py` 负责合并严格、放宽和可选库存候选，按 `result_id` 去重并标记来源；`cli/eval.py` 负责为 `prepare` 提供严格、放宽及仅限 `detail` 的无关键词库存调用。`score` 继续直接使用原始 `SearchEvalCase`，不读取候选文件。

**Tech Stack:** Python 3.10+、dataclasses、Typer、PyYAML、pytest。

---

## 文件结构与职责

- `src/novel_material/eval/search_eval.py`：扩展候选导出接口，按需调用放宽与库存检索、合并、去重、截断并写入 `candidate_source`。
- `src/novel_material/cli/eval.py`：只在 `prepare` 中构造 `filters={}` 的放宽查询和 `detail query=""` 的库存查询；评分路径不变。
- `tests/eval/test_search_eval.py`：验证补足、去重、来源标记和无需补足时不调用放宽检索。
- `tests/eval/test_search_eval_cli.py`：验证 `prepare` 传入放宽检索，`score` 仍拒绝未标注查询。
- `eval/search_candidates.yaml`：重新生成的人工工作文件，不提交。

### Task 1：实现候选补足与来源标记

**Files:**
- Modify: `src/novel_material/eval/search_eval.py`
- Modify: `tests/eval/test_search_eval.py`

- [ ] **Step 1: 编写严格结果足够时不调用放宽检索的失败测试**

```python
def test_export_candidates_skips_relaxed_search_when_strict_pool_is_large_enough(tmp_path):
    cases = [SearchEvalCase("chapter_001", "开局困境", "chapter", {}, {}, True, True)]
    strict = [_result(f"chapter:nm_demo:{index}") for index in range(1, 11)]

    def unexpected_relaxed(_case, _limit):
        raise AssertionError("严格候选足够时不应执行放宽检索")

    output = tmp_path / "candidates.yaml"
    export_candidates(
        cases,
        lambda _case, _limit: strict,
        output,
        limit=30,
        minimum_candidates=10,
        relaxed_search_callable=unexpected_relaxed,
    )
    rows = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert len(rows) == 10
    assert {row["candidate_source"] for row in rows} == {"strict"}
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/eval/test_search_eval.py::test_export_candidates_skips_relaxed_search_when_strict_pool_is_large_enough -v`

Expected: FAIL，提示 `export_candidates()` 不接受 `minimum_candidates` 或 `relaxed_search_callable`。

- [ ] **Step 3: 编写严格不足时补足并去重的失败测试**

```python
def test_export_candidates_backfills_from_relaxed_search_and_deduplicates(tmp_path):
    cases = [SearchEvalCase("chapter_001", "开局困境", "chapter", {"chapter_num": 1}, {}, True, True)]
    strict = [_result("chapter:nm_demo:1"), _result("chapter:nm_demo:2")]
    relaxed = [
        _result("chapter:nm_demo:2"),
        _result("chapter:nm_other:3", material_id="nm_other"),
        _result("chapter:nm_other:4", material_id="nm_other"),
    ]
    output = tmp_path / "candidates.yaml"

    export_candidates(
        cases,
        lambda _case, _limit: strict,
        output,
        limit=4,
        minimum_candidates=4,
        relaxed_search_callable=lambda _case, _limit: relaxed,
    )
    rows = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert [row["result_id"] for row in rows] == [
        "chapter:nm_demo:1",
        "chapter:nm_demo:2",
        "chapter:nm_other:3",
        "chapter:nm_other:4",
    ]
    assert [row["candidate_source"] for row in rows] == [
        "strict", "strict", "relaxed", "relaxed"
    ]
```

- [ ] **Step 4: 实现最小候选池合并**

将 `export_candidates` 签名扩展为：

```python
def export_candidates(
    cases: list[SearchEvalCase],
    search_callable: SearchCallable,
    output_path: Path,
    limit: int = 30,
    *,
    minimum_candidates: int = 10,
    relaxed_search_callable: SearchCallable | None = None,
) -> None:
```

每个 case 的实现规则：

```python
strict_results = search_callable(case, limit)[:limit]
pool = [(result, "strict") for result in strict_results]
seen = {result.result_id for result in strict_results}

if len(pool) < minimum_candidates and relaxed_search_callable is not None:
    for result in relaxed_search_callable(case, limit):
        if result.result_id in seen:
            continue
        seen.add(result.result_id)
        pool.append((result, "relaxed"))
        if len(pool) >= min(limit, minimum_candidates):
            break
```

写入普通候选时增加 `candidate_source`；零结果占位记录保持 `status: no_candidates`，并增加 `candidate_source: none`。函数开始时验证 `1 <= minimum_candidates <= limit`，否则抛出 `ValueError`。

- [ ] **Step 5: 运行评测核心测试**

Run: `python -m pytest tests/eval/test_search_eval.py -v`

Expected: 全部 PASS；既有候选导出测试更新为断言 `candidate_source: strict`。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/eval/search_eval.py tests/eval/test_search_eval.py
git commit -m "feat(eval): 补足人工标注候选" -m "主要改动：
- 严格候选不足时合并放宽检索结果
- 按 result_id 去重并记录候选来源

验证结果：
- python -m pytest tests/eval/test_search_eval.py -v：通过"
```

### Task 2：接入 prepare 放宽检索并验证真实候选

**Files:**
- Modify: `src/novel_material/cli/eval.py`
- Modify: `tests/eval/test_search_eval_cli.py`
- Regenerate: `eval/search_candidates.yaml`（不提交）

- [ ] **Step 1: 编写 CLI 传入放宽查询的失败测试**

在 `test_eval_prepare_exports_candidates` 中记录 `_search_case` 收到的 filters：

```python
observed_filters = []

def fake_search(case, _limit, _mode):
    observed_filters.append(case.filters)
    if case.filters:
        return []
    return [SearchResult(
        result_id="chapter:nm_demo:1",
        document_type="chapter",
        material_id="nm_demo",
        title="开篇",
        summary="主角陷入困境。",
    )]

monkeypatch.setattr("novel_material.cli.eval._search_case", fake_search)
```

把测试查询改成 `filters: {chapter_num: 1}`，执行 `prepare` 后断言：

```python
assert observed_filters == [{"chapter_num": 1}, {}]
rows = yaml.safe_load(output.read_text(encoding="utf-8"))
assert rows[0]["candidate_source"] == "relaxed"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/eval/test_search_eval_cli.py::test_eval_prepare_exports_candidates -v`

Expected: FAIL；当前 `prepare` 只调用一次严格检索。

- [ ] **Step 3: 实现 CLI 放宽调用**

导入 `dataclasses.replace`，在 `prepare` 调用中增加：

```python
relaxed_search_callable=lambda case, candidate_limit: _search_case(
    replace(case, filters={}),
    candidate_limit,
    mode,
),
minimum_candidates=min(10, limit),
```

`score` 函数保持原样，不传 `relaxed_search_callable`，也不读取候选 YAML。

- [ ] **Step 4: 运行 CLI 专项与全量测试**

Run: `python -m pytest tests/eval/test_search_eval_cli.py -v && python -m pytest -q`

Expected: CLI 专项全部 PASS；全量不少于 `97 passed, 1 skipped`。

- [ ] **Step 5: 重新导出真实候选**

Run:

```bash
python -m novel_material.cli.main eval search prepare \
  --queries eval/search_queries.yaml \
  --output eval/search_candidates.yaml \
  --limit 30
```

Expected: 30 个 case 均保留；每条候选包含 `candidate_source`。统计每个 case 的真实候选数，目标至少 10；若底层实体总量不足，报告实际缺口，不复制候选。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/cli/eval.py tests/eval/test_search_eval_cli.py
git commit -m "feat(eval): 接入放宽候选检索" -m "主要改动：
- prepare 在严格候选不足时移除过滤条件补足标注池
- score 继续使用原始过滤条件与精确检索语义

验证结果：
- python -m pytest tests/eval/test_search_eval_cli.py -v：通过
- python -m pytest -q：通过"
```

### Task 3：为 detail 增加库存候选兜底

**Files:**
- Modify: `src/novel_material/eval/search_eval.py`
- Modify: `src/novel_material/cli/eval.py`
- Modify: `tests/eval/test_search_eval.py`
- Modify: `tests/eval/test_search_eval_cli.py`
- Regenerate: `eval/search_candidates.yaml`（不提交）

- [ ] **Step 1: 编写库存候选合并失败测试**

```python
def test_export_candidates_backfills_from_inventory_after_relaxed_pool(tmp_path):
    cases = [SearchEvalCase("detail_001", "感情线节拍", "detail", {}, {}, True, False)]
    inventory = [_detail_result(f"detail:nm_demo:1:{index}") for index in range(1, 4)]
    output = tmp_path / "candidates.yaml"

    export_candidates(
        cases,
        lambda _case, _limit: [],
        output,
        limit=3,
        minimum_candidates=3,
        relaxed_search_callable=lambda _case, _limit: [],
        inventory_search_callable=lambda _case, _limit: inventory,
    )
    rows = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert len(rows) == 3
    assert {row["candidate_source"] for row in rows} == {"inventory"}
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/eval/test_search_eval.py::test_export_candidates_backfills_from_inventory_after_relaxed_pool -v`

Expected: FAIL，提示 `export_candidates()` 不接受 `inventory_search_callable`。

- [ ] **Step 3: 实现库存候选合并**

为 `export_candidates` 增加关键字参数：

```python
inventory_search_callable: SearchCallable | None = None,
```

放宽候选合并后仍不足目标数量时，按相同 `seen` 集合去重合并库存结果并标记 `inventory`。严格、放宽或库存任一路达到目标数量后停止后续调用。

- [ ] **Step 4: 编写 detail 专用库存调度失败测试**

新增 CLI 测试，构造 `document_type: detail`、`query: 感情线节拍`。让 fake `_search_case` 只在 `query == ""` 时返回一个 detail 结果，执行 `prepare --limit 1` 后断言调用顺序为：

```python
[("感情线节拍", {}), ("感情线节拍", {}), ("", {})]
```

并断言导出候选的 `candidate_source == "inventory"`。

- [ ] **Step 5: 实现 detail 专用库存调度**

在 `cli/eval.py` 新增：

```python
def _search_inventory_case(case: SearchEvalCase, limit: int, mode: str):
    if case.document_type != "detail":
        return []
    return _search_case(replace(case, query="", filters={}), limit, mode)
```

`prepare` 传入：

```python
inventory_search_callable=lambda case, candidate_limit: _search_inventory_case(
    case, candidate_limit, mode
),
```

- [ ] **Step 6: 运行专项与全量测试**

Run: `python -m pytest tests/eval/test_search_eval.py tests/eval/test_search_eval_cli.py -v && python -m pytest -q`

Expected: 专项全部通过；全量不少于 `99 passed, 1 skipped`。

- [ ] **Step 7: 重新导出并统计真实候选**

Run:

```bash
python -m novel_material.cli.main eval search prepare \
  --queries eval/search_queries.yaml \
  --output eval/search_candidates.yaml \
  --limit 30
```

Expected: `detail_001` 至少 10 条真实候选且来源为 `inventory`；30 个 case 均至少 10 条，不复制结果。

- [ ] **Step 8: 提交**

```bash
git add src/novel_material/eval/search_eval.py src/novel_material/cli/eval.py tests/eval/test_search_eval.py tests/eval/test_search_eval_cli.py
git commit -m "feat(eval): 为细纲补充库存候选" -m "主要改动：
- detail 严格与放宽候选不足时使用无关键词库存补足
- 库存候选记录独立来源且不进入 exact 评分

验证结果：
- 搜索评测专项测试：通过
- python -m pytest -q：通过"
```

### Task 4：恢复 Task 6 人工标注检查点

**Files:**
- Modify manually: `eval/search_candidates.yaml`
- Modify via command: `eval/search_queries.yaml`
- Create via command: `eval/baselines/4096-exact.json`

- [ ] **Step 1: 核查候选数量**

每个 case 至少标注 10 个候选，并包含至少 3 个 0 分困难负例。若仍有 case 少于 10 个真实候选，停止并报告具体 case 与数量。

- [ ] **Step 2: 等待用户完成人工标注**

用户将 `eval/search_candidates.yaml` 中每条候选的 `relevance` 填为 0、1、2 或 3；禁止 Agent 猜测相关性。

- [ ] **Step 3: 导入标签**

Run:

```bash
python -m novel_material.cli.main eval search import-labels \
  --queries eval/search_queries.yaml \
  --candidates eval/search_candidates.yaml
```

Expected: 30 个 case 的 `status` 变为 `labeled`，所有 judgments 非空且分数位于 0～3。

- [ ] **Step 4: 保存 4096 维精确基线**

Run:

```bash
python -m novel_material.cli.main eval search score \
  --queries eval/search_queries.yaml \
  --mode exact \
  --output eval/baselines/4096-exact.json
```

Expected: 报告包含 30 条逐查询结果、按文档类型聚合和总体宏平均；评分检索继续使用原始 filters。
