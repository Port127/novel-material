# Resilient Enrichment Phase 2 Worldbuilding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single-shot worldbuilding extraction with dimension-level extraction, repair, and conservative stats-seeded fallback.

**Architecture:** Keep the existing layered worldbuilding files, but split generation into dimension units before writing. `pipeline/worldbuilding.py` orchestrates the stage, new helper modules build dimension jobs and stats-seeded entities, and `worldbuilding/normalizer.py` remains the final schema boundary.

**Tech Stack:** Python 3.12, existing YAML helpers, existing worldbuilding layered models, pytest, no real LLM calls in tests.

---

## Dependencies

Phase 2 depends on Phase 1 only for configurable LLM timeout cap. It does not depend on the new character quality fields.

## File Structure

- Create: `src/novel_material/pipeline/worldbuilding_jobs.py` for dimension job construction.
- Create: `src/novel_material/pipeline/worldbuilding_fallback.py` for `stats_seeded` entity generation.
- Modify: `src/novel_material/pipeline/worldbuilding.py` to call dimension jobs instead of one global extraction.
- Modify: `src/novel_material/worldbuilding/models.py` if `source_quality` and `dimension_id` fields are missing.
- Modify: `src/novel_material/worldbuilding/writer.py` to persist `dimension_status` and `source_quality_counts`.
- Modify: `src/novel_material/audit/rules.py` to treat all-empty worldbuilding as error and partial dimensions as warning.
- Modify: `src/novel_material/reporting/models.py` and `src/novel_material/reporting/markdown.py` to display dimension quality.
- Test: `tests/pipeline/test_worldbuilding_layered_pipeline.py`
- Test: `tests/pipeline/test_worldbuilding_stage_result.py`
- Test: `tests/worldbuilding/test_writer.py`
- Test: `tests/audit/test_rules.py`
- Test: `tests/reporting/test_markdown.py`

## Task 1: Build Dimension Jobs

**Files:**
- Create: `src/novel_material/pipeline/worldbuilding_jobs.py`
- Test: `tests/pipeline/test_worldbuilding_layered_pipeline.py`

- [ ] **Step 1: Add failing test**

Append:

```python
from novel_material.pipeline.worldbuilding_jobs import build_worldbuilding_jobs


def test_build_worldbuilding_jobs_uses_applicable_dimensions_only():
    dimensions = [
        {"id": "organizations", "applicability": "applicable", "name": "组织"},
        {"id": "power_system", "applicability": "not_applicable", "name": "力量体系"},
    ]

    jobs = build_worldbuilding_jobs(dimensions, context_text="摘要", context_label="章级摘要池")

    assert [job.dimension_id for job in jobs] == ["organizations"]
    assert jobs[0].context_text == "摘要"
    assert jobs[0].context_label == "章级摘要池"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pytest tests/pipeline/test_worldbuilding_layered_pipeline.py::test_build_worldbuilding_jobs_uses_applicable_dimensions_only -v
```

Expected: fail with `ModuleNotFoundError`.

- [ ] **Step 3: Implement jobs module**

Create:

```python
"""Worldbuilding dimension job construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorldbuildingJob:
    dimension_id: str
    dimension_name: str
    context_text: str
    context_label: str


def build_worldbuilding_jobs(
    dimensions: list[dict[str, Any]],
    *,
    context_text: str,
    context_label: str,
) -> list[WorldbuildingJob]:
    jobs: list[WorldbuildingJob] = []
    for dimension in dimensions:
        if dimension.get("applicability") != "applicable":
            continue
        jobs.append(
            WorldbuildingJob(
                dimension_id=str(dimension.get("id") or ""),
                dimension_name=str(dimension.get("name") or dimension.get("id") or ""),
                context_text=context_text,
                context_label=context_label,
            )
        )
    return [job for job in jobs if job.dimension_id]


__all__ = ["WorldbuildingJob", "build_worldbuilding_jobs"]
```

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/pipeline/test_worldbuilding_layered_pipeline.py::test_build_worldbuilding_jobs_uses_applicable_dimensions_only -v
```

Expected: pass.

## Task 2: Add Stats-Seeded Fallback Entities

**Files:**
- Create: `src/novel_material/pipeline/worldbuilding_fallback.py`
- Test: `tests/pipeline/test_worldbuilding_layered_pipeline.py`

- [ ] **Step 1: Add failing test**

Append:

```python
from novel_material.pipeline.worldbuilding_fallback import build_stats_seeded_entities


def test_build_stats_seeded_entities_creates_conservative_entities():
    stats = {
        "organizations": {"黑星军团": 12},
        "locations": {"海蓝星": 7},
    }

    entities = build_stats_seeded_entities(stats, min_count=5)

    by_name = {entity["name"]: entity for entity in entities}
    assert by_name["黑星军团"]["source_quality"] == "stats_seeded"
    assert by_name["黑星军团"]["type"] == "organization"
    assert by_name["海蓝星"]["type"] == "location"
    assert by_name["海蓝星"]["confidence"] == 0.45
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pytest tests/pipeline/test_worldbuilding_layered_pipeline.py::test_build_stats_seeded_entities_creates_conservative_entities -v
```

Expected: fail with `ModuleNotFoundError`.

- [ ] **Step 3: Implement fallback module**

Create:

```python
"""Conservative worldbuilding fallback from chapter-level statistics."""

from __future__ import annotations

from typing import Any


def build_stats_seeded_entities(
    stats: dict[str, dict[str, int]],
    *,
    min_count: int = 5,
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    type_map = {"organizations": "organization", "locations": "location"}
    for bucket, entity_type in type_map.items():
        for name, count in sorted(stats.get(bucket, {}).items(), key=lambda item: (-item[1], item[0])):
            if count < min_count:
                continue
            entities.append(
                {
                    "type": entity_type,
                    "name": name,
                    "description": f"从章级分析统计生成的基础实体，出现 {count} 次，待 LLM 补全。",
                    "importance": "primary" if count >= 10 else "secondary",
                    "source_quality": "stats_seeded",
                    "confidence": 0.45,
                    "evidence": [
                        {
                            "chapter": 1,
                            "basis": "fact",
                            "summary": "章级分析统计中高频出现该实体。",
                        }
                    ],
                }
            )
    return entities


__all__ = ["build_stats_seeded_entities"]
```

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/pipeline/test_worldbuilding_layered_pipeline.py::test_build_stats_seeded_entities_creates_conservative_entities -v
```

Expected: pass.

## Task 3: Orchestrate Dimension-Level Extraction

**Files:**
- Modify: `src/novel_material/pipeline/worldbuilding.py`
- Test: `tests/pipeline/test_worldbuilding_layered_pipeline.py`
- Test: `tests/pipeline/test_worldbuilding_stage_result.py`

- [ ] **Step 1: Add stage behavior test**

Append:

```python
def test_worldbuilding_dimension_failure_keeps_successful_dimension(tmp_path, monkeypatch):
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "name": "示例", "genre": ["科幻"]})
    save_yaml(novel / "chapter_index.yaml", [{"chapter": 1, "title": "一"}])
    save_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "黑星军团在海蓝星行动", "setting": ["海蓝星"]}])

    calls = []

    def fake_call_llm(*_args, **kwargs):
        calls.append(kwargs.get("context", ""))
        if "locations" in kwargs.get("context", ""):
            raise RuntimeError("timeout")
        return {
            "overview": {"world_summary": "组织推动剧情", "driving_mechanisms": []},
            "dimensions": [],
            "entities": [
                {
                    "type": "organization",
                    "name": "黑星军团",
                    "description": "核心组织",
                    "importance": "primary",
                    "evidence": [{"chapter": 1, "basis": "fact", "summary": "出现"}],
                }
            ],
            "relations": [],
        }

    monkeypatch.setattr("novel_material.pipeline.worldbuilding.NOVELS_DIR", tmp_path)
    monkeypatch.setattr("novel_material.pipeline.worldbuilding.call_llm", fake_call_llm)
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.load_config",
        lambda _provider=None: {"llm": {"worldbuilding_timeout": 1, "rate_limit_seconds": 0, "worldbuilding_summary_tokens": 1000}},
    )
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.build_analysis_context",
        lambda *_args, **_kwargs: ("黑星军团在海蓝星行动", "章级摘要池"),
    )

    result = generate_worldbuilding("nm_demo")

    assert result.status.value in {"success", "degraded"}
    assert result.outputs["entity_count"] >= 1
    assert result.outputs["dimension_status"]["locations"] in {"stats_seeded", "missing"}
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pytest tests/pipeline/test_worldbuilding_layered_pipeline.py::test_worldbuilding_dimension_failure_keeps_successful_dimension -v
```

Expected: fail because current stage uses one global call and cannot preserve one dimension while another fails.

- [ ] **Step 3: Implement dimension loop**

In `generate_worldbuilding()`, after `dimension_routing` and `context_text` are available:

```python
from novel_material.pipeline.worldbuilding_jobs import build_worldbuilding_jobs
from novel_material.pipeline.worldbuilding_fallback import build_stats_seeded_entities
```

Build jobs from `dimension_routing.dimensions`, call LLM per job, merge normalized entities and relations into a single payload, and set:

```python
dimension_status: dict[str, str] = {}
```

For each job:

```python
try:
    payload = call_llm(
        system_prompt,
        user_prompt,
        config,
        max_tokens_override=config["llm"].get("worldbuilding_max_tokens"),
        timeout_override=config["llm"]["worldbuilding_timeout"],
        context=f"{material_id} 世界观#{job.dimension_id}",
    )
    normalized = normalize_layered_worldbuilding_response(payload)
    dimension_status[job.dimension_id] = "llm_verified"
except Exception:
    dimension_status[job.dimension_id] = "missing"
```

If no LLM entities are produced for `organizations` or `locations`, append `build_stats_seeded_entities(wb_stats)` and mark corresponding dimension as `stats_seeded` when entities were added.

- [ ] **Step 4: Persist dimension status**

Pass `dimension_status` into the layered model or write it into `_index.yaml` through writer support. If models are frozen and do not yet support this field, add optional fields to `LayeredWorldbuildingIndex` in `src/novel_material/worldbuilding/models.py`:

```python
dimension_status: dict[str, str] = Field(default_factory=dict)
source_quality_counts: dict[str, int] = Field(default_factory=dict)
```

- [ ] **Step 5: Run worldbuilding tests**

Run:

```bash
pytest tests/pipeline/test_worldbuilding_layered_pipeline.py tests/pipeline/test_worldbuilding_stage_result.py tests/worldbuilding/test_writer.py -v
```

Expected: all tests pass.

## Task 4: Report And Audit Dimension Quality

**Files:**
- Modify: `src/novel_material/audit/rules.py`
- Modify: `src/novel_material/reporting/models.py`
- Modify: `src/novel_material/reporting/markdown.py`
- Test: `tests/audit/test_rules.py`
- Test: `tests/reporting/test_markdown.py`

- [ ] **Step 1: Add audit assertion**

Append a test where `_index.yaml` has `entity_count: 0`, `llm_success: false`, and `dimension_status` with all applicable dimensions `missing`. Expected: an `error` issue code `worldbuilding_empty`.

- [ ] **Step 2: Add reporting fields**

Extend `WorldbuildingQualityReport` with:

```python
dimension_status: dict[str, str] = Field(default_factory=dict)
source_quality_counts: dict[str, int] = Field(default_factory=dict)
```

- [ ] **Step 3: Update markdown**

After the existing worldbuilding summary line, add a line with:

```python
f"- 世界观维度：{quality.worldbuilding_quality.dimension_status or {}}"
```

- [ ] **Step 4: Run verification**

Run:

```bash
pytest tests/audit/test_rules.py tests/reporting/test_markdown.py -v
```

Expected: all tests pass.

## Phase 2 Acceptance Criteria

- One failed worldbuilding dimension does not erase successful dimensions.
- Empty worldbuilding with `llm_success: false` is never reported as success.
- High-frequency organizations and locations can become `stats_seeded` entities when LLM extraction fails.
- Reports show dimension status and source quality distribution.
- Tests use fake LLM calls only.
