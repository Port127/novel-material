# Resilient Enrichment Phase 3 Profile Insights Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `profile`, `insights`, `validate`, and `release_gate` consume Phase 1/2 quality signals and produce actionable, quality-first outcomes.

**Architecture:** `work_profile` becomes a limited/full profile generator instead of an all-or-nothing schema gate. `insights` preserves successful chapters and repairs missing/invalid chapters individually. Validation and release gate classify issues by severity and output quality-restoring next actions.

**Tech Stack:** Python 3.12, Pydantic profile models, existing insight validation, pytest, no real LLM calls in tests.

---

## Dependencies

Phase 3 depends on:

- Phase 1 `characters/_index.yaml.quality_counts`
- Phase 2 `worldbuilding/_index.yaml.dimension_status`
- Phase 1 timeout config exposing `profile_timeout` and `insights_timeout`

## File Structure

- Modify: `src/novel_material/pipeline/work_profile_models.py`
- Modify: `src/novel_material/pipeline/work_profile.py`
- Modify: `src/novel_material/pipeline/work_profile_prompt.py`
- Modify: `src/novel_material/pipeline/insights.py`
- Modify: `src/novel_material/pipeline/release_gate.py`
- Modify: `src/novel_material/validation/validators.py`
- Modify: `src/novel_material/reporting/models.py`
- Modify: `src/novel_material/reporting/markdown.py`
- Test: `tests/pipeline/test_work_profile_contract.py`
- Test: `tests/pipeline/test_work_profile_stage.py`
- Test: `tests/pipeline/test_insights_pipeline.py`
- Test: `tests/pipeline/test_release_gate.py`
- Test: `tests/validation/test_schema.py`
- Test: `tests/reporting/test_markdown.py`

## Task 1: Allow Limited Work Profiles

**Files:**
- Modify: `src/novel_material/pipeline/work_profile_models.py`
- Test: `tests/pipeline/test_work_profile_contract.py`

- [ ] **Step 1: Add failing model test**

Append:

```python
from novel_material.pipeline.work_profile_models import normalize_work_profile_response


def test_work_profile_allows_limited_quality_with_limitations():
    profile = normalize_work_profile_response(
        {
            "quality_level": "limited",
            "core_hooks": ["NPC 视角"],
            "reader_expectations": ["升级爽点"],
            "story_structure": {"pacing_pattern": "阶段推进"},
            "evidence_index": {"chapters": [1]},
            "limitations": ["世界观部分来自统计兜底"],
            "confidence": 0.55,
        },
        material_id="nm_demo",
        title="示例",
    )

    assert profile.quality_level == "limited"
    assert profile.limitations == ("世界观部分来自统计兜底",)
```

- [ ] **Step 2: Run failing test**

Run:

```bash
pytest tests/pipeline/test_work_profile_contract.py::test_work_profile_allows_limited_quality_with_limitations -v
```

Expected: fail because `quality_level` is not in `WorkProfile`.

- [ ] **Step 3: Add quality_level field**

In `WorkProfile`, add:

```python
quality_level: str = "full"
```

Add this validator:

```python
@field_validator("quality_level")
@classmethod
def validate_quality_level(cls, value: str) -> str:
    if value not in {"full", "limited"}:
        raise ValueError("quality_level 必须是 full 或 limited")
    return value
```

Remember to import `field_validator` from `pydantic`.

- [ ] **Step 4: Verify**

Run:

```bash
pytest tests/pipeline/test_work_profile_contract.py -v
```

Expected: all tests pass.

## Task 2: Generate Limited Profile Instead Of Failing Schema Once

**Files:**
- Modify: `src/novel_material/pipeline/work_profile.py`
- Modify: `src/novel_material/pipeline/work_profile_prompt.py`
- Test: `tests/pipeline/test_work_profile_stage.py`

- [ ] **Step 1: Add stage test**

Append:

```python
def test_generate_work_profile_repairs_missing_evidence_index_as_limited(tmp_path, monkeypatch):
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "name": "示例"})
    save_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "主角登场"}])

    calls = []

    def fake_call_llm(*_args, **_kwargs):
        calls.append(1)
        if len(calls) == 1:
            return {"core_hooks": ["开局"], "reader_expectations": ["爽点"], "confidence": 0.5}
        return {
            "quality_level": "limited",
            "core_hooks": ["开局"],
            "reader_expectations": ["爽点"],
            "story_structure": {"pacing_pattern": "快节奏"},
            "evidence_index": {"chapters": [1]},
            "limitations": ["首次响应缺少证据索引，已修复为 limited"],
            "confidence": 0.5,
        }

    monkeypatch.setattr("novel_material.pipeline.work_profile.NOVELS_DIR", tmp_path)
    monkeypatch.setattr("novel_material.pipeline.work_profile.call_llm", fake_call_llm)
    monkeypatch.setattr("novel_material.pipeline.work_profile.load_config", lambda _provider=None: {"llm": {"profile_timeout": 1}})

    result = generate_work_profile("nm_demo")

    assert result.status.value == "success"
    assert load_yaml(novel / "work_profile.yaml")["quality_level"] == "limited"
```

- [ ] **Step 2: Implement one repair attempt**

In `generate_work_profile()`, when `normalize_work_profile_response()` raises `ValueError`, call LLM once more with a repair prompt that includes:

```text
原始响应
错误信息
必须补 evidence_index
如果前置证据不足，quality_level 写 limited 并说明 limitations
```

If repair succeeds, save `work_profile.yaml`. If repair fails, keep existing `work_profile_schema_invalid` failure.

- [ ] **Step 3: Verify**

Run:

```bash
pytest tests/pipeline/test_work_profile_stage.py -v
```

Expected: all tests pass.

## Task 3: Preserve Insight Successes And Repair Missing Chapters

**Files:**
- Modify: `src/novel_material/pipeline/insights.py`
- Test: `tests/pipeline/test_insights_pipeline.py`

- [ ] **Step 1: Add insight repair test**

Append:

```python
def test_insights_preserves_successful_chapters_and_repairs_missing(tmp_path, monkeypatch):
    material_id = "nm_demo"
    novel = tmp_path / material_id
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": material_id, "name": "示例", "genre": ["科幻"]})
    save_yaml(
        novel / "chapters.yaml",
        [
            {"chapter": 1, "title": "一", "summary": "主角登场", "key_event": "登场"},
            {"chapter": 2, "title": "二", "summary": "组织冲突", "key_event": "冲突"},
        ],
    )
    calls = []

    def fake_call_llm(*_args, **_kwargs):
        calls.append(_kwargs.get("context", ""))
        if len(calls) == 1:
            return {
                "insights": [
                    {
                        "chapter": 1,
                        "profiles": ["common"],
                        "core_scene": "主角登场",
                        "craft_points": ["快速建立目标"],
                    }
                ]
            }
        return {
            "insights": [
                {
                    "chapter": 2,
                    "profiles": ["common"],
                    "core_scene": "组织冲突",
                    "craft_points": ["用冲突推进设定"],
                }
            ]
        }

    monkeypatch.setattr("novel_material.pipeline.insights.NOVELS_DIR", tmp_path)
    monkeypatch.setattr("novel_material.pipeline.insights.call_llm", fake_call_llm)
    monkeypatch.setattr(
        "novel_material.pipeline.insights.load_config",
        lambda _provider=None: {"llm": {"insight_batch_size": 2, "insights_timeout": 1}},
    )

    success = generate_chapter_insights(material_id, start=1, end=2)

    assert success is True
    assert (novel / "chapter_insights" / "0001.yaml").is_file()
    assert (novel / "chapter_insights" / "0002.yaml").is_file()
```

If the current insight schema requires additional required fields, add the smallest valid values to the two fake response objects in this test. Do not remove the assertion that both output files exist.

- [ ] **Step 2: Implement missing-chapter repair**

In `generate_chapter_insights()`, after batch validation:

```python
missing = expected_chapters - returned_chapters
for chapter in missing:
    repair_result = call_llm(
        system_prompt,
        single_chapter_prompt,
        config,
        max_tokens_override=config["llm"].get("insights_max_tokens"),
        timeout_override=config["llm"].get("insights_timeout", config["llm"].get("other_timeout")),
        context=f"{material_id} insights修复#{chapter['chapter']}",
    )
    validate and save that chapter only
```

Track:

```python
insight_quality = {
    "expected": expected_count,
    "succeeded": succeeded_count,
    "repaired": repaired_count,
    "failed": failed_count,
    "missing_after_repair": missing_after_repair,
}
```

- [ ] **Step 3: Verify**

Run:

```bash
pytest tests/pipeline/test_insights_pipeline.py tests/validation/test_insights.py -v
```

Expected: all tests pass.

## Task 4: Make Release Gate Next Actions Specific

**Files:**
- Modify: `src/novel_material/pipeline/release_gate.py`
- Modify: `src/novel_material/reporting/models.py`
- Test: `tests/pipeline/test_release_gate.py`

- [ ] **Step 1: Add release gate test**

Append:

```python
def test_release_gate_next_actions_are_stage_specific():
    result = evaluate_release_gate(
        material_id="nm_demo",
        mode="standard",
        stages=[
            _stage("characters", "degraded", ["character_biography_all_failed"]),
            _stage("worldbuilding", "degraded", ["worldbuilding_api_failed"]),
            _stage("profile", "failed", ["work_profile_schema_invalid"]),
        ],
        audit_issues=[],
        allow_degraded_sync=False,
    )

    assert result.decision == "block"
    assert "nm pipeline characters nm_demo" in result.next_actions
    assert "nm pipeline worldbuilding nm_demo" in result.next_actions
    assert "nm pipeline profile nm_demo" in result.next_actions
```

If `tests/pipeline/test_release_gate.py` uses a different helper name than `_stage`, create a local `_stage(name, status, diagnostic_codes)` helper in the test file that returns the stage object expected by `evaluate_release_gate`.

- [ ] **Step 2: Implement action mapping**

In `release_gate.py`, add mapping:

```python
NEXT_ACTIONS_BY_REASON = {
    "audit_error": "nm validate artifacts <material_id> --review",
    "profile_failed": "nm pipeline profile <material_id>",
    "worldbuilding_degraded": "nm pipeline worldbuilding <material_id>",
    "characters_degraded": "nm pipeline characters <material_id>",
    "insights_degraded": "nm pipeline insights <material_id>",
}
```

Return formatted actions with the real `material_id`.

- [ ] **Step 3: Verify**

Run:

```bash
pytest tests/pipeline/test_release_gate.py tests/reporting/test_builder.py -v
```

Expected: all tests pass.

## Task 5: Soften Unknown Chapter Function Tags Into Review Items

**Files:**
- Modify: `src/novel_material/validation/validators.py`
- Test: `tests/validation/test_schema.py`

- [ ] **Step 1: Add validation test**

Append:

```python
def test_unknown_chapter_functions_are_review_warnings_not_schema_crash(tmp_path, monkeypatch):
    material_id = "nm_demo"
    novel = tmp_path / material_id
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": material_id, "name": "示例"})
    save_yaml(
        novel / "chapters.yaml",
        [
            {
                "chapter": 1,
                "title": "一",
                "summary": "主角登场",
                "chapter_functions": ["开篇建立"],
            }
        ],
    )

    monkeypatch.setattr("novel_material.validation.validators.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.validation.validators.validate_tags_batch",
        lambda _dimension, tags: ([], list(tags)),
    )

    errors = validate_material(material_id)

    assert not any("chapter_functions" in error and "不在标签字典中" in error for error in errors)
```

Import `save_yaml` and `validate_material` at the top of `tests/validation/test_schema.py` if they are not already imported.

- [ ] **Step 2: Implement canonical handling**

In chapter tag validation, classify unknown `chapter_functions` as review items unless the field is required for storage contract. Keep strict behavior for schema-breaking fields.

- [ ] **Step 3: Verify**

Run:

```bash
pytest tests/validation/test_schema.py -v
```

Expected: all tests pass.

## Phase 3 Acceptance Criteria

- `work_profile.yaml` can be written with `quality_level: limited` when upstream evidence is partial.
- `profile` still fails when even repair cannot produce `evidence_index`.
- `insights` saves successful chapters before repairing missing or invalid chapters.
- `release_gate` emits concrete quality-restoring next actions.
- Unknown generated chapter function tags no longer create thousands of hard schema errors.
