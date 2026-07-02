# Resilient Enrichment Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first anti-failure slice for long-form enrichment: configurable LLM timeout caps, resilient core character biography extraction, and quality reporting that avoids whole-batch fallback.

**Architecture:** Keep existing pipeline entry points intact, but add focused helpers for character quality classification and core biography repair. `characters_layer.py` remains responsible for LLM batch calls, `characters_biography.py` owns response normalization, `characters_core.py` owns saved profile/index aggregation, and reporting reads quality counters from stage outputs and audit artifacts.

**Tech Stack:** Python 3.12, Typer CLI, Pydantic models, pytest, existing YAML helpers, existing OpenAI-compatible LLM wrapper.

---

## Scope Check

The approved design covers five subsystems: `characters`, `worldbuilding`, `profile`, `insights`, and `validate/release_gate`. This plan intentionally implements only Phase 1:

- `characters` small batches, layered schema, per-character preservation, and repair hooks.
- LLM timeout configuration needed by `characters` and later phases.
- Reporting additions needed to see `full/enriched/partial/fallback` quality distribution.

`worldbuilding`, `profile` degradation behavior, `insights` single-chapter repair, and tag canonicalization must be implemented in separate plans after this one lands.

## File Structure

- Modify `config/settings.yaml`: add timeout cap and character batch/repair defaults.
- Modify `src/novel_material/infra/config_service.py`: expose new config keys.
- Modify `src/novel_material/infra/llm.py`: use configurable SDK timeout cap.
- Create `src/novel_material/pipeline/characters_quality.py`: quality levels, issue attachment, counters, and profile quality classification.
- Modify `src/novel_material/pipeline/characters_biography.py`: add lenient core biography normalization while preserving strict `normalize_biography_response()` compatibility.
- Create `src/novel_material/pipeline/characters_repair.py`: build repair prompts and normalize repaired single-character payloads.
- Modify `src/novel_material/pipeline/characters_layer.py`: use role-specific batch sizes, preserve valid characters from partial batches, repair invalid core characters, fallback only failed candidates.
- Modify `src/novel_material/pipeline/characters_core.py`: write quality counts and repair counts to `_index.yaml` and stage outputs.
- Modify `src/novel_material/reporting/models.py`: add character quality count fields.
- Modify `src/novel_material/reporting/markdown.py`: display quality distribution and repair counts.
- Modify `src/novel_material/audit/rules.py`: treat `enriched` and `partial` differently from `fallback`.
- Test files:
  - `tests/infra/test_config_service.py`
  - `tests/infra/test_llm_contracts.py`
  - `tests/pipeline/test_character_biography.py`
  - `tests/pipeline/test_characters_pipeline_biographies.py`
  - `tests/pipeline/test_characters_stage_result.py`
  - `tests/reporting/test_markdown.py`
  - `tests/audit/test_rules.py`

## Task 1: Add Timeout And Character Batch Configuration

**Files:**
- Modify: `config/settings.yaml`
- Modify: `src/novel_material/infra/config_service.py`
- Modify: `src/novel_material/infra/llm.py`
- Test: `tests/infra/test_config_service.py`
- Test: `tests/infra/test_llm_contracts.py`

- [ ] **Step 1: Write config exposure tests**

Append to `tests/infra/test_config_service.py`:

```python
def test_build_llm_config_exposes_resilient_enrichment_keys() -> None:
    config = _build_llm_config(
        {
            "LLM_SDK_TIMEOUT_CAP": 1200,
            "LLM_PROFILE_TIMEOUT": 1800,
            "LLM_INSIGHTS_TIMEOUT": 1200,
            "LLM_CORE_CHARACTER_BATCH_SIZE": 2,
            "LLM_SUPPORTING_CHARACTER_BATCH_SIZE": 12,
            "LLM_MINOR_CHARACTER_BATCH_SIZE": 20,
            "LLM_CHARACTER_REPAIR_MAX_ATTEMPTS": 1,
        },
        providers_yaml=None,
        provider=None,
    )

    assert config["sdk_timeout_cap"] == 1200
    assert config["profile_timeout"] == 1800
    assert config["insights_timeout"] == 1200
    assert config["core_character_batch_size"] == 2
    assert config["supporting_character_batch_size"] == 12
    assert config["minor_character_batch_size"] == 20
    assert config["character_repair_max_attempts"] == 1
```

- [ ] **Step 2: Run config test to verify it fails**

Run:

```bash
pytest tests/infra/test_config_service.py::test_build_llm_config_exposes_resilient_enrichment_keys -v
```

Expected: fail with `KeyError: 'sdk_timeout_cap'`.

- [ ] **Step 3: Expose config values**

In `src/novel_material/infra/config_service.py`, inside `_build_llm_config()`, add these keys near the existing timeout and budget fields:

```python
"sdk_timeout_cap": int(settings.get("LLM_SDK_TIMEOUT_CAP", 300)),
"profile_timeout": int(settings.get("LLM_PROFILE_TIMEOUT", settings.get("LLM_OTHER_TIMEOUT", 120))),
"insights_timeout": int(settings.get("LLM_INSIGHTS_TIMEOUT", settings.get("LLM_OTHER_TIMEOUT", 120))),
"core_character_batch_size": int(settings.get("LLM_CORE_CHARACTER_BATCH_SIZE", 2)),
"supporting_character_batch_size": int(settings.get("LLM_SUPPORTING_CHARACTER_BATCH_SIZE", 12)),
"minor_character_batch_size": int(settings.get("LLM_MINOR_CHARACTER_BATCH_SIZE", 20)),
"character_repair_max_attempts": int(settings.get("LLM_CHARACTER_REPAIR_MAX_ATTEMPTS", 1)),
```

- [ ] **Step 4: Add defaults to settings**

In `config/settings.yaml`, add:

```yaml
LLM_SDK_TIMEOUT_CAP: 1200
LLM_PROFILE_TIMEOUT: 1800
LLM_INSIGHTS_TIMEOUT: 1200

LLM_CORE_CHARACTER_BATCH_SIZE: 2
LLM_SUPPORTING_CHARACTER_BATCH_SIZE: 12
LLM_MINOR_CHARACTER_BATCH_SIZE: 20
LLM_CHARACTER_REPAIR_MAX_ATTEMPTS: 1
```

Place timeout keys under the existing LLM timeout section. Place character batch keys under the LLM batch processing section.

- [ ] **Step 5: Update SDK timeout cap**

In `src/novel_material/infra/llm.py`, replace:

```python
sdk_timeout = min(total_timeout * 0.8, 300)
```

with:

```python
sdk_timeout_cap = int(config["llm"].get("sdk_timeout_cap", 300))
sdk_timeout = min(total_timeout * 0.8, sdk_timeout_cap)
```

- [ ] **Step 6: Run config tests**

Run:

```bash
pytest tests/infra/test_config_service.py tests/infra/test_llm_contracts.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 1**

```bash
git add config/settings.yaml src/novel_material/infra/config_service.py src/novel_material/infra/llm.py tests/infra/test_config_service.py tests/infra/test_llm_contracts.py
git commit -m "feat(config): 增加增强阶段超时与批次配置" -m "主要改动：
- 暴露 LLM_SDK_TIMEOUT_CAP、LLM_PROFILE_TIMEOUT 和 LLM_INSIGHTS_TIMEOUT。
- 暴露核心、配角、次要人物批次大小和人物 repair 次数配置。
- LLM 调用层使用可配置 SDK timeout cap。

验证结果：
- pytest tests/infra/test_config_service.py tests/infra/test_llm_contracts.py -v 通过。"
```

## Task 2: Add Character Quality Helpers

**Files:**
- Create: `src/novel_material/pipeline/characters_quality.py`
- Test: `tests/pipeline/test_character_biography.py`

- [ ] **Step 1: Write quality helper tests**

Append to `tests/pipeline/test_character_biography.py`:

```python
from novel_material.pipeline.characters_quality import (
    build_character_quality_counts,
    classify_profile_quality,
    mark_schema_issue,
)


def test_character_quality_classifies_full_enriched_partial_and_fallback():
    full = {"name": "甲", "profile_level": "full", "biography_complete": True}
    enriched = {"name": "乙", "profile_level": "enriched", "biography_complete": False}
    partial = {"name": "丙", "profile_level": "partial", "schema_issues": ["缺少 psychology"]}
    fallback = {"name": "丁", "profile_level": "fallback"}

    assert classify_profile_quality(full) == "full"
    assert classify_profile_quality(enriched) == "enriched"
    assert classify_profile_quality(partial) == "partial"
    assert classify_profile_quality(fallback) == "fallback"

    counts = build_character_quality_counts([full, enriched, partial, fallback])
    assert counts == {"full": 1, "enriched": 1, "partial": 1, "fallback": 1}


def test_mark_schema_issue_records_source_quality_and_attempt_count():
    profile = {"name": "丙"}

    result = mark_schema_issue(
        profile,
        issue="psychology 缺失",
        level="partial",
        source_quality="llm_repaired",
        repair_attempts=1,
    )

    assert result["profile_level"] == "partial"
    assert result["source_quality"] == "llm_repaired"
    assert result["repair_attempts"] == 1
    assert result["schema_issues"] == ["psychology 缺失"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/pipeline/test_character_biography.py::test_character_quality_classifies_full_enriched_partial_and_fallback tests/pipeline/test_character_biography.py::test_mark_schema_issue_records_source_quality_and_attempt_count -v
```

Expected: fail with `ModuleNotFoundError: No module named 'novel_material.pipeline.characters_quality'`.

- [ ] **Step 3: Create quality helper module**

Create `src/novel_material/pipeline/characters_quality.py`:

```python
"""人物档案质量分级与诊断字段工具。"""

from __future__ import annotations

from typing import Any

QUALITY_LEVELS = ("full", "enriched", "partial", "fallback")


def classify_profile_quality(profile: dict[str, Any]) -> str:
    """返回人物档案质量等级，未知等级按 partial 处理。"""
    level = profile.get("profile_level")
    if level in QUALITY_LEVELS:
        return str(level)
    if profile.get("biography_complete") is True:
        return "full"
    if profile.get("schema_issues"):
        return "partial"
    return "fallback"


def build_character_quality_counts(
    profiles: list[dict[str, Any]],
) -> dict[str, int]:
    """统计人物档案质量分布。"""
    counts = {level: 0 for level in QUALITY_LEVELS}
    for profile in profiles:
        counts[classify_profile_quality(profile)] += 1
    return counts


def mark_schema_issue(
    profile: dict[str, Any],
    *,
    issue: str,
    level: str,
    source_quality: str,
    repair_attempts: int,
) -> dict[str, Any]:
    """给档案添加 schema 诊断信息，返回新 dict。"""
    result = dict(profile)
    issues = list(result.get("schema_issues") or [])
    issues.append(issue)
    result["schema_issues"] = issues
    result["profile_level"] = level
    result["source_quality"] = source_quality
    result["repair_attempts"] = repair_attempts
    if level != "full":
        result["biography_complete"] = False
    return result


__all__ = [
    "QUALITY_LEVELS",
    "build_character_quality_counts",
    "classify_profile_quality",
    "mark_schema_issue",
]
```

- [ ] **Step 4: Run quality helper tests**

Run:

```bash
pytest tests/pipeline/test_character_biography.py::test_character_quality_classifies_full_enriched_partial_and_fallback tests/pipeline/test_character_biography.py::test_mark_schema_issue_records_source_quality_and_attempt_count -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/novel_material/pipeline/characters_quality.py tests/pipeline/test_character_biography.py
git commit -m "feat(characters): 增加人物档案质量分级工具" -m "主要改动：
- 新增 characters_quality 模块，支持 full、enriched、partial、fallback 分级。
- 新增 schema issue 标记和质量分布统计。

验证结果：
- pytest tests/pipeline/test_character_biography.py::test_character_quality_classifies_full_enriched_partial_and_fallback tests/pipeline/test_character_biography.py::test_mark_schema_issue_records_source_quality_and_attempt_count -v 通过。"
```

## Task 3: Add Lenient Core Biography Normalization

**Files:**
- Modify: `src/novel_material/pipeline/characters_biography.py`
- Test: `tests/pipeline/test_character_biography.py`

- [ ] **Step 1: Write lenient normalization tests**

Append to `tests/pipeline/test_character_biography.py`:

```python
from novel_material.pipeline.characters_biography import normalize_biography_candidates


def test_lenient_biography_normalization_preserves_valid_and_invalid_candidates():
    valid = _full_profile()
    invalid = {"name": "沈幼楚", "role": "supporting", "description": "重要角色"}

    result = normalize_biography_candidates(
        {"characters": [valid, invalid]},
        candidate_names={"陈汉升", "沈幼楚"},
    )

    assert [profile["name"] for profile in result.valid_profiles] == ["陈汉升"]
    assert result.invalid_profiles[0].name == "沈幼楚"
    assert result.invalid_profiles[0].raw["description"] == "重要角色"
    assert result.invalid_profiles[0].issues


def test_lenient_biography_normalization_marks_missing_candidate():
    result = normalize_biography_candidates(
        {"characters": [_full_profile()]},
        candidate_names={"陈汉升", "沈幼楚"},
    )

    assert result.missing_names == ("沈幼楚",)
```

- [ ] **Step 2: Run lenient normalization tests to verify they fail**

Run:

```bash
pytest tests/pipeline/test_character_biography.py::test_lenient_biography_normalization_preserves_valid_and_invalid_candidates tests/pipeline/test_character_biography.py::test_lenient_biography_normalization_marks_missing_candidate -v
```

Expected: fail with `ImportError: cannot import name 'normalize_biography_candidates'`.

- [ ] **Step 3: Add result dataclasses and lenient function**

In `src/novel_material/pipeline/characters_biography.py`, import dataclass:

```python
from dataclasses import dataclass
```

Add before `normalize_biography_response()`:

```python
@dataclass(frozen=True)
class InvalidBiographyProfile:
    name: str
    raw: dict[str, Any]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class BiographyNormalizationResult:
    valid_profiles: list[dict[str, Any]]
    invalid_profiles: list[InvalidBiographyProfile]
    missing_names: tuple[str, ...]
```

Add function after `normalize_biography_response()`:

```python
def normalize_biography_candidates(
    payload: object,
    candidate_names: set[str],
) -> BiographyNormalizationResult:
    """宽松规范化完整小传响应，保留同批有效人物和失败人物。"""
    raw = (
        payload
        if isinstance(payload, list)
        else require_mapping(payload, "characters").get("characters")
    )
    characters = require_mapping_list(raw, "characters")
    valid_profiles: list[dict[str, Any]] = []
    invalid_profiles: list[InvalidBiographyProfile] = []
    seen_names: set[str] = set()

    for index, character in enumerate(characters):
        raw_profile = dict(character)
        name = str(raw_profile.get("name") or "").strip()
        if name:
            seen_names.add(name)
        try:
            normalized = normalize_biography_response(
                {"characters": [raw_profile]},
                candidate_names,
            )
        except Exception as exc:
            invalid_profiles.append(
                InvalidBiographyProfile(
                    name=name or f"characters[{index}]",
                    raw=raw_profile,
                    issues=(str(exc),),
                )
            )
            continue
        valid_profiles.extend(normalized)

    missing_names = tuple(sorted(candidate_names - seen_names))
    return BiographyNormalizationResult(
        valid_profiles=valid_profiles,
        invalid_profiles=invalid_profiles,
        missing_names=missing_names,
    )
```

Update `__all__`:

```python
__all__ = [
    "BiographyNormalizationResult",
    "InvalidBiographyProfile",
    "normalize_biography_candidates",
    "normalize_biography_response",
]
```

- [ ] **Step 4: Run biography tests**

Run:

```bash
pytest tests/pipeline/test_character_biography.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/novel_material/pipeline/characters_biography.py tests/pipeline/test_character_biography.py
git commit -m "feat(characters): 支持核心人物宽松小传规范化" -m "主要改动：
- 新增 normalize_biography_candidates，保留同批有效人物。
- 记录无效人物原始 payload、错误信息和漏返名单。
- 保留原 strict normalize_biography_response 兼容现有调用。

验证结果：
- pytest tests/pipeline/test_character_biography.py -v 通过。"
```

## Task 4: Add Core Biography Repair Helper

**Files:**
- Create: `src/novel_material/pipeline/characters_repair.py`
- Test: `tests/pipeline/test_character_biography.py`

- [ ] **Step 1: Write repair helper tests**

Append to `tests/pipeline/test_character_biography.py`:

```python
from novel_material.pipeline.characters_repair import repair_core_biography_profile


def test_repair_core_biography_profile_returns_repaired_profile(monkeypatch):
    raw = {"name": "沈幼楚", "role": "supporting", "description": "重要角色"}

    def fake_call_llm(*_args, **_kwargs):
        fixed = _full_profile()
        fixed["name"] = "沈幼楚"
        return {"characters": [fixed]}

    monkeypatch.setattr("novel_material.pipeline.characters_repair.call_llm", fake_call_llm)

    repaired = repair_core_biography_profile(
        raw_profile=raw,
        issues=("arc_stages 缺失",),
        candidate_names={"沈幼楚"},
        config={"llm": {"characters_timeout": 1}},
        material_id="nm_demo",
        context_label="摘要池",
        context_text="第1章：沈幼楚登场",
    )

    assert repaired["name"] == "沈幼楚"
    assert repaired["profile_level"] == "full"
    assert repaired["biography_complete"] is True
    assert repaired["source_quality"] == "llm_repaired"
    assert repaired["repair_attempts"] == 1
```

- [ ] **Step 2: Run repair helper test to verify it fails**

Run:

```bash
pytest tests/pipeline/test_character_biography.py::test_repair_core_biography_profile_returns_repaired_profile -v
```

Expected: fail with `ModuleNotFoundError: No module named 'novel_material.pipeline.characters_repair'`.

- [ ] **Step 3: Create repair module**

Create `src/novel_material/pipeline/characters_repair.py`:

```python
"""核心人物小传 repair 调用。"""

from __future__ import annotations

import json
from typing import Any

from novel_material.infra.llm import call_llm
from novel_material.pipeline.characters_biography import normalize_biography_response


def repair_core_biography_profile(
    *,
    raw_profile: dict[str, Any],
    issues: tuple[str, ...],
    candidate_names: set[str],
    config: dict,
    material_id: str,
    context_label: str,
    context_text: str,
) -> dict[str, Any]:
    """对单个核心人物小传做格式修复，返回 strict-normalized profile。"""
    system_prompt = """你是小说人物档案 JSON 修复器。只修复结构和缺失字段，不新增候选名单之外的人物。
必须返回 {"characters": [{"name": "角色名"}]} 形态，数组中只能有一个人物。"""
    user_prompt = f"""请修复以下人物档案，使其符合完整小传 schema。

候选名单：{sorted(candidate_names)}
错误列表：{list(issues)}

原始档案：
{json.dumps(raw_profile, ensure_ascii=False)}

{context_label}：
{context_text}
"""
    response = call_llm(
        system_prompt,
        user_prompt,
        config,
        max_tokens_override=4000,
        timeout_override=config["llm"]["characters_timeout"],
        context=f"{material_id} 人物小传repair#{raw_profile.get('name', 'unknown')}",
    )
    normalized = normalize_biography_response(response, candidate_names)
    repaired = dict(normalized[0])
    repaired["source_quality"] = "llm_repaired"
    repaired["repair_attempts"] = 1
    return repaired


__all__ = ["repair_core_biography_profile"]
```

- [ ] **Step 4: Run repair helper test**

Run:

```bash
pytest tests/pipeline/test_character_biography.py::test_repair_core_biography_profile_returns_repaired_profile -v
```

Expected: pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/novel_material/pipeline/characters_repair.py tests/pipeline/test_character_biography.py
git commit -m "feat(characters): 增加核心人物小传 repair 工具" -m "主要改动：
- 新增单人物小传 repair prompt 和 strict normalize。
- repair 成功后标记 source_quality 和 repair_attempts。

验证结果：
- pytest tests/pipeline/test_character_biography.py::test_repair_core_biography_profile_returns_repaired_profile -v 通过。"
```

## Task 5: Preserve Valid Core Characters And Fallback Only Failed Candidates

**Files:**
- Modify: `src/novel_material/pipeline/characters_layer.py`
- Test: `tests/pipeline/test_characters_pipeline_biographies.py`

- [ ] **Step 1: Write extraction behavior tests**

Append to `tests/pipeline/test_characters_pipeline_biographies.py`:

```python
from novel_material.pipeline.characters_layer import _extract_character_batch


def test_core_extraction_preserves_valid_profile_when_same_batch_has_invalid(monkeypatch):
    candidates = [("陈汉升", 10), ("沈幼楚", 9)]
    calls = []

    def fake_call_llm(*_args, **_kwargs):
        calls.append(_kwargs.get("context", ""))
        return {
            "characters": [
                {
                    "name": "陈汉升",
                    "role": "protagonist",
                    "archetype": "重生者",
                    "moral_spectrum": "灰色",
                    "identity": "学生",
                    "life_summary": "重生后重新选择。",
                    "external_goal": "创业",
                    "internal_need": "承担责任",
                    "fear": "重蹈覆辙",
                    "fatal_flaw": "自负",
                    "contradiction": "功利与真心冲突",
                    "arc_stages": [{"stage": "opening", "change": "破局", "evidence": {"chapters": [1]}}],
                    "description": "核心人物",
                    "arc_summary": "从逃避走向承担",
                    "narrative_function": "推动主线",
                    "psychology": {"motivation": "改变命运"},
                    "first_appearance_chapter": 1,
                    "key_events": [{"chapter": 1, "description": "重生"}],
                    "relationships": [],
                    "habits": [],
                    "speech_style": "调侃",
                    "interaction_patterns": [],
                    "key_scenes": [{"chapter": 1, "event": "重生", "function": "开篇"}],
                    "craft_notes": [{"technique": "反差", "boundary": "不照搬"}],
                    "confidence": 0.8,
                    "basis": "fact",
                },
                {"name": "沈幼楚", "role": "supporting", "description": "缺字段"},
            ]
        }

    monkeypatch.setattr("novel_material.pipeline.characters_layer.call_llm", fake_call_llm)
    monkeypatch.setattr(
        "novel_material.pipeline.characters_layer.repair_core_biography_profile",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("repair failed")),
    )

    profiles = _extract_character_batch(
        candidates,
        "core",
        "第1章：人物登场",
        "摘要池",
        {"theme": ["都市"]},
        {"llm": {"characters_timeout": 1, "rate_limit_seconds": 0, "character_repair_max_attempts": 1}},
        material_id="nm_demo",
        batch_size=2,
        chapters_data=[{"chapter": 1, "characters_appear": ["沈幼楚"], "key_event": "沈幼楚登场"}],
    )

    by_name = {profile["name"]: profile for profile in profiles}
    assert by_name["陈汉升"]["profile_level"] == "full"
    assert by_name["沈幼楚"]["profile_level"] in {"partial", "fallback"}
    assert len(profiles) == 2
```

- [ ] **Step 2: Run extraction test to verify current failure**

Run:

```bash
pytest tests/pipeline/test_characters_pipeline_biographies.py::test_core_extraction_preserves_valid_profile_when_same_batch_has_invalid -v
```

Expected: fail because current code catches the invalid character exception and falls back the whole batch.

- [ ] **Step 3: Update imports**

In `src/novel_material/pipeline/characters_layer.py`, change imports:

```python
from novel_material.pipeline.characters_biography import (
    normalize_biography_candidates,
    normalize_biography_response,
)
from novel_material.pipeline.characters_quality import mark_schema_issue
from novel_material.pipeline.characters_repair import repair_core_biography_profile
```

- [ ] **Step 4: Use role-specific batch sizes**

In `_extract_character_batch()`, replace:

```python
if batch_size is None:
    batch_size = CHARACTER_BATCH_SIZE
```

with:

```python
if batch_size is None:
    llm_config = config.get("llm", {})
    if role_tier == "core":
        batch_size = int(llm_config.get("core_character_batch_size", 2))
    elif role_tier == "supporting":
        batch_size = int(llm_config.get("supporting_character_batch_size", CHARACTER_BATCH_SIZE))
    else:
        batch_size = int(llm_config.get("minor_character_batch_size", CHARACTER_BATCH_SIZE))
```

- [ ] **Step 5: Replace core branch normalization**

Inside the successful LLM call block, replace:

```python
if role_tier == "core":
    characters = normalize_biography_response(result, candidate_names)
else:
    characters = normalize_characters_response(result, candidate_names)
```

with:

```python
if role_tier == "core":
    normalized_result = normalize_biography_candidates(result, candidate_names)
    characters = list(normalized_result.valid_profiles)
    repair_attempts = int(config["llm"].get("character_repair_max_attempts", 1))
    if repair_attempts > 0:
        for invalid in normalized_result.invalid_profiles:
            if invalid.name not in candidate_names:
                continue
            try:
                characters.append(
                    repair_core_biography_profile(
                        raw_profile=invalid.raw,
                        issues=invalid.issues,
                        candidate_names={invalid.name},
                        config=config,
                        material_id=material_id,
                        context_label=context_label,
                        context_text=context_text,
                    )
                )
            except Exception as repair_error:
                logger.error(f"{prefix}核心人物 {invalid.name} repair 失败: {repair_error}")
                count = dict(batch_candidates).get(invalid.name, 0)
                fallback = _build_basic_profile_from_stats(invalid.name, count, valid_roles[0], chapters_data or [])
                fallback = mark_schema_issue(
                    fallback,
                    issue="; ".join(invalid.issues),
                    level="partial",
                    source_quality="llm_partial",
                    repair_attempts=repair_attempts,
                )
                characters.append(fallback)
    for missing_name in normalized_result.missing_names:
        count = dict(batch_candidates).get(missing_name, 0)
        fallback = _build_basic_profile_from_stats(missing_name, count, valid_roles[0], chapters_data or [])
        fallback = mark_schema_issue(
            fallback,
            issue="LLM 未返回该核心人物",
            level="fallback",
            source_quality="stats_seeded",
            repair_attempts=0,
        )
        characters.append(fallback)
else:
    characters = normalize_characters_response(result, candidate_names)
```

- [ ] **Step 6: Run extraction test**

Run:

```bash
pytest tests/pipeline/test_characters_pipeline_biographies.py::test_core_extraction_preserves_valid_profile_when_same_batch_has_invalid -v
```

Expected: pass.

- [ ] **Step 7: Run character pipeline tests**

Run:

```bash
pytest tests/pipeline/test_character_biography.py tests/pipeline/test_characters_pipeline_biographies.py tests/pipeline/test_characters_stage_result.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 5**

```bash
git add src/novel_material/pipeline/characters_layer.py tests/pipeline/test_characters_pipeline_biographies.py
git commit -m "feat(characters): 避免核心人物整批 fallback" -m "主要改动：
- 核心人物使用角色层级批次配置。
- 核心人物同批中有效档案立即保存，失败人物单独 repair 或 fallback。
- 漏返人物只对该人物生成 fallback，不影响同批其他人物。

验证结果：
- pytest tests/pipeline/test_character_biography.py tests/pipeline/test_characters_pipeline_biographies.py tests/pipeline/test_characters_stage_result.py -v 通过。"
```

## Task 6: Add Character Quality Counts To Stage Outputs And Reports

**Files:**
- Modify: `src/novel_material/pipeline/characters_core.py`
- Modify: `src/novel_material/reporting/models.py`
- Modify: `src/novel_material/reporting/markdown.py`
- Test: `tests/pipeline/test_characters_stage_result.py`
- Test: `tests/reporting/test_markdown.py`

- [ ] **Step 1: Write stage output test**

Append to `tests/pipeline/test_characters_stage_result.py`:

```python
from novel_material.pipeline.characters_quality import build_character_quality_counts


def test_build_character_quality_counts_used_for_stage_outputs():
    profiles = [
        {"name": "甲", "profile_level": "full"},
        {"name": "乙", "profile_level": "enriched"},
        {"name": "丙", "profile_level": "partial"},
        {"name": "丁", "profile_level": "fallback"},
    ]

    assert build_character_quality_counts(profiles) == {
        "full": 1,
        "enriched": 1,
        "partial": 1,
        "fallback": 1,
    }
```

- [ ] **Step 2: Update characters core index and outputs**

In `src/novel_material/pipeline/characters_core.py`, import:

```python
from novel_material.pipeline.characters_quality import build_character_quality_counts
```

Before the existing `char_index` dictionary is constructed in `generate_characters()`, add:

```python
quality_counts = build_character_quality_counts(all_characters)
repair_counts = {
    "attempted": sum(1 for c in all_characters if int(c.get("repair_attempts") or 0) > 0),
    "succeeded": sum(
        1
        for c in all_characters
        if int(c.get("repair_attempts") or 0) > 0 and c.get("source_quality") == "llm_repaired"
    ),
    "failed": sum(
        1
        for c in all_characters
        if int(c.get("repair_attempts") or 0) > 0 and c.get("source_quality") != "llm_repaired"
    ),
}
```

Inside `char_index`, add:

```python
"quality_counts": quality_counts,
"repair_counts": repair_counts,
```

Inside returned `outputs`, add:

```python
"quality_counts": quality_counts,
"repair_counts": repair_counts,
```

- [ ] **Step 3: Extend report model**

In `src/novel_material/reporting/models.py`, add fields to `CharacterQualityReport`:

```python
full_profile_count: int = Field(default=0, ge=0)
enriched_profile_count: int = Field(default=0, ge=0)
partial_profile_count: int = Field(default=0, ge=0)
fallback_profile_count: int = Field(default=0, ge=0)
repair_attempted_count: int = Field(default=0, ge=0)
repair_succeeded_count: int = Field(default=0, ge=0)
repair_failed_count: int = Field(default=0, ge=0)
```

- [ ] **Step 4: Extend markdown output**

In `src/novel_material/reporting/markdown.py`, after the existing `完整小传` line, add:

```python
(
    "- 人物质量："
    f"full={quality.character_quality.full_profile_count}，"
    f"enriched={quality.character_quality.enriched_profile_count}，"
    f"partial={quality.character_quality.partial_profile_count}，"
    f"fallback={quality.character_quality.fallback_profile_count}，"
    f"repair={quality.character_quality.repair_succeeded_count}/"
    f"{quality.character_quality.repair_attempted_count}"
)
```

- [ ] **Step 5: Run reporting tests**

Run:

```bash
pytest tests/pipeline/test_characters_stage_result.py tests/reporting/test_markdown.py -v
```

Expected: all tests pass. If `test_markdown` asserts exact text, update the expected string to include this literal prefix: `- 人物质量：full=`。

- [ ] **Step 6: Commit Task 6**

```bash
git add src/novel_material/pipeline/characters_core.py src/novel_material/reporting/models.py src/novel_material/reporting/markdown.py tests/pipeline/test_characters_stage_result.py tests/reporting/test_markdown.py
git commit -m "feat(reporting): 展示人物档案质量分布" -m "主要改动：
- characters 阶段输出 quality_counts 和 repair_counts。
- 报告模型增加 full/enriched/partial/fallback 和 repair 计数字段。
- Markdown 报告展示人物质量分布。

验证结果：
- pytest tests/pipeline/test_characters_stage_result.py tests/reporting/test_markdown.py -v 通过。"
```

## Task 7: Adjust Audit Rules For Enriched And Partial Profiles

**Files:**
- Modify: `src/novel_material/audit/rules.py`
- Test: `tests/audit/test_rules.py`

- [ ] **Step 1: Write audit behavior test**

Append to `tests/audit/test_rules.py`:

```python
def test_character_audit_treats_partial_less_severely_than_fallback(tmp_path):
    from novel_material.audit.models import AuditContext
    from novel_material.audit.rules import check_character_profiles
    from novel_material.infra.yaml_io import save_yaml

    novel = tmp_path / "nm_demo"
    profiles = novel / "characters" / "profiles"
    profiles.mkdir(parents=True)
    save_yaml(
        profiles / "甲_000.yaml",
        {
            "name": "甲",
            "role": "protagonist",
            "profile_level": "partial",
            "biography_complete": False,
            "schema_issues": ["psychology 缺失"],
            "description": "核心人物",
        },
    )
    save_yaml(
        profiles / "乙_001.yaml",
        {
            "name": "乙",
            "role": "protagonist",
            "profile_level": "fallback",
            "biography_complete": False,
            "description": "统计兜底",
        },
    )

    issues = list(check_character_profiles(AuditContext(material_id="nm_demo", novel_dir=novel)))
    by_artifact = {issue.artifact: issue for issue in issues}

    assert by_artifact["characters/profiles/甲_000.yaml"].severity.value == "warning"
    assert by_artifact["characters/profiles/乙_001.yaml"].severity.value == "error"
```

- [ ] **Step 2: Run audit test to verify current behavior**

Run:

```bash
pytest tests/audit/test_rules.py::test_character_audit_treats_partial_less_severely_than_fallback -v
```

Expected: fail if `partial` is currently treated like fallback or missing issue.

- [ ] **Step 3: Update audit rule**

In `src/novel_material/audit/rules.py`, locate `check_character_profiles()`. Add explicit handling:

```python
if profile_level == "fallback":
    severity = IssueSeverity.ERROR if role in {"protagonist", "antagonist"} else IssueSeverity.WARNING
elif profile_level == "partial":
    severity = IssueSeverity.WARNING
elif profile_level == "enriched":
    severity = IssueSeverity.INFO if profile.get("schema_issues") else None
else:
    severity = None
```

When `severity is not None`, emit the existing `character_profile_fallback` issue code for fallback and a new `character_profile_partial` code for partial/enriched schema issues.

- [ ] **Step 4: Run audit tests**

Run:

```bash
pytest tests/audit/test_rules.py -v
```

Expected: all audit rule tests pass.

- [ ] **Step 5: Commit Task 7**

```bash
git add src/novel_material/audit/rules.py tests/audit/test_rules.py
git commit -m "feat(audit): 区分 partial 与 fallback 人物档案" -m "主要改动：
- fallback 核心人物仍按 error 处理。
- partial 人物档案按 warning 处理并保留 schema_issues 证据。
- enriched 档案仅在仍有 schema_issues 时进入低风险提示。

验证结果：
- pytest tests/audit/test_rules.py -v 通过。"
```

## Task 8: Run Phase 1 Verification

**Files:**
- No source edits expected.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
pytest tests/infra/test_config_service.py tests/infra/test_llm_contracts.py tests/pipeline/test_character_biography.py tests/pipeline/test_characters_pipeline_biographies.py tests/pipeline/test_characters_stage_result.py tests/reporting/test_markdown.py tests/audit/test_rules.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Run pipeline-related regression tests**

Run:

```bash
pytest tests/pipeline/test_unattended_pipeline_regression.py tests/pipeline/test_release_gate.py tests/reporting/test_builder.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Inspect git status**

Run:

```bash
git status --short
```

Expected: no unstaged source changes from Phase 1. Existing unrelated user changes may remain, but Phase 1 files should be clean after task commits.

- [ ] **Step 4: Commit verification note if needed**

If documentation needs a short implementation note, update `docs/superpowers/execution/` with the executed commands and commit it. If no note is added, do not create an empty commit.

## Phase 1 Acceptance Criteria

- Core character extraction no longer falls back an entire batch because one person failed schema validation.
- Valid core profiles in a mixed-validity batch are preserved as `full`.
- Failed core profiles are repaired once when configured, then saved as `full`, `enriched`, `partial`, or `fallback`.
- `characters/_index.yaml` includes `quality_counts` and `repair_counts`.
- Run reports can display `full/enriched/partial/fallback` and repair success count.
- `LLM_SDK_TIMEOUT_CAP`, `LLM_PROFILE_TIMEOUT`, `LLM_INSIGHTS_TIMEOUT`, and character batch settings are available through `config["llm"]`.
- Focused tests pass without real LLM calls, database connections, or edits to real素材.
