# Resilient Enrichment Phase 4 Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the repaired enrichment pipeline on fixtures first, then on `nm_novel_20260701_7u96` only after project mechanisms are fixed.

**Architecture:** Verification is evidence collection, not feature development. Use synthetic tests and read-only reports first; only run real LLM stages when the user explicitly authorizes the cost and the preceding phases pass.

**Tech Stack:** Existing `nm` CLI, pytest, run reports under `data/novels/<material_id>/reports`, no manual YAML edits.

---

## Dependencies

Phase 4 depends on Phase 1, Phase 2, and Phase 3 being implemented and committed.

## Verification Rules

- Do not manually edit `chapters/*.yaml`, `chapter_insights/*.yaml`, `characters/profiles/*.yaml`, or `worldbuilding/*.yaml`.
- Do not run `nm pipeline full` on `nm_novel_20260701_7u96`.
- Prefer targeted reruns: `characters`, `worldbuilding`, `profile`, `insights`, `audit`.
- If an LLM stage requires real API calls, ask the user for explicit approval before running it.

## Task 1: Run Full Focused Test Suite

**Files:**
- No edits expected.

- [ ] **Step 1: Run phase-focused tests**

Run:

```bash
pytest tests/infra/test_config_service.py tests/infra/test_llm_contracts.py tests/pipeline/test_character_biography.py tests/pipeline/test_characters_pipeline_biographies.py tests/pipeline/test_characters_stage_result.py tests/pipeline/test_worldbuilding_layered_pipeline.py tests/pipeline/test_worldbuilding_stage_result.py tests/pipeline/test_work_profile_contract.py tests/pipeline/test_work_profile_stage.py tests/pipeline/test_insights_pipeline.py tests/pipeline/test_release_gate.py tests/audit/test_rules.py tests/reporting/test_markdown.py tests/validation/test_schema.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Run regression tests**

Run:

```bash
pytest tests/pipeline/test_unattended_pipeline_regression.py tests/reporting/test_builder.py tests/search/test_contracts.py -v
```

Expected: all tests pass.

## Task 2: Inspect Existing Material Read-Only

**Files:**
- No edits expected.

- [ ] **Step 1: Check current status**

Run:

```bash
nm pipeline status nm_novel_20260701_7u96
```

Expected: existing report may still show degraded/failed because material has not been rerun.

- [ ] **Step 2: Read latest report**

Run:

```bash
sed -n '1,220p' data/novels/nm_novel_20260701_7u96/reports/latest.md
```

Expected: confirms pre-fix baseline issues for comparison.

## Task 3: Ask Before Real Reruns

**Files:**
- No edits expected.

- [ ] **Step 1: Present targeted rerun proposal**

Ask the user to approve this exact sequence:

```bash
nm pipeline characters nm_novel_20260701_7u96
nm pipeline worldbuilding nm_novel_20260701_7u96
nm pipeline profile nm_novel_20260701_7u96
nm pipeline insights nm_novel_20260701_7u96
nm pipeline continue nm_novel_20260701_7u96 --skip-sync
```

Explain that this spends API to improve quality after mechanisms are fixed. Do not frame it as minimizing API cost.

- [ ] **Step 2: Run only approved stages**

Run only the commands approved by the user. If a command fails due to sandbox/network restrictions, request escalation according to project policy.

## Task 4: Compare Quality After Rerun

**Files:**
- Create: `docs/archive/analysis/nm_novel_20260701_7u96_resilient_enrichment_verification.md`

- [ ] **Step 1: Collect post-rerun status**

Run:

```bash
nm pipeline status nm_novel_20260701_7u96
sed -n '1,260p' data/novels/nm_novel_20260701_7u96/reports/latest.md
```

- [ ] **Step 2: Write verification report**

Create the report with sections:

```markdown
# nm_novel_20260701_7u96 抗失败增强验证

## 验证命令

## Characters 质量变化

## Worldbuilding 质量变化

## Profile 状态

## Insights 状态

## Release Gate 结论

## 是否建议同步
```

- [ ] **Step 3: Commit verification report**

```bash
git add docs/archive/analysis/nm_novel_20260701_7u96_resilient_enrichment_verification.md
git commit -m "docs: 记录超神机械师抗失败增强验证" -m "主要改动：
- 记录 nm_novel_20260701_7u96 在抗失败增强后的 targeted rerun 结果。
- 对比 characters、worldbuilding、profile、insights 和 release_gate 状态。

验证结果：
- 已记录实际执行的 nm 命令和报告结论。"
```

## Phase 4 Acceptance Criteria

- No real novel rerun occurs before Phase 1-3 are complete.
- Any real rerun is targeted and explicitly approved.
- Verification report records commands, quality changes, and sync recommendation.
- No manual YAML edits are used to make the material pass.
