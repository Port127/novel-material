# Resilient Enrichment Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the full resilient enrichment effort visible across multiple implementation plans so execution does not stop after Phase 1.

**Architecture:** This roadmap is the coordination layer above the phase-specific plans. Each phase must be independently shippable, but later phases consume quality signals produced by earlier phases.

**Tech Stack:** Markdown planning docs, existing Novel Material Python pipeline, pytest, existing run reporting and audit models.

---

## Quality Principle

API usage is not a quality constraint. The project should spend the calls needed to produce high-quality artifacts. The waste to avoid is rerunning expensive stages before fixing the project mechanisms that caused empty, fallback, or schema-invalid outputs.

## Phase Overview

| Phase | Plan file | Primary objective | Depends on | Must produce |
|---|---|---|---|---|
| Phase 1 | `docs/superpowers/plans/2026-07-02-resilient-enrichment-phase1.md` | `characters` 小批次、分层 schema、单人物 repair、timeout cap、人物质量报告 | Existing design only | `quality_counts`、`repair_counts`、可配置 timeout cap |
| Phase 2 | `docs/superpowers/plans/2026-07-02-resilient-enrichment-phase2-worldbuilding.md` | `worldbuilding` 分维度抽取、维度级 repair、`stats_seeded` 兜底 | Phase 1 timeout config | `dimension_status`、非空 stats entities、维度级 diagnostics |
| Phase 3 | `docs/superpowers/plans/2026-07-02-resilient-enrichment-phase3-profile-insights-gate.md` | `profile` 降级生成、`insights` 单章 repair、`validate/release_gate` 分级 | Phase 1 quality counts, Phase 2 worldbuilding statuses | `work_profile.quality_level`、`insight_quality`、actionable gate next actions |
| Phase 4 | `docs/superpowers/plans/2026-07-02-resilient-enrichment-phase4-verification.md` | 用事故素材做授权验证，不在机制修复前重跑 | Phase 1-3 completed | 验证报告、是否可重跑的明确结论 |

## Execution Rules

- [ ] **Rule 1: Execute plans in order**

Run Phase 1 before Phase 2. Run Phase 2 before Phase 3. Run Phase 4 only after Phase 1-3 are implemented and verified.

- [ ] **Rule 2: Do not rerun real novels before Phase 1-3**

Before Phase 1-3 complete, only use synthetic fixtures and unit tests. Existing materials such as `nm_novel_20260701_7u96` may be inspected read-only, but must not be reprocessed as a substitute for fixing project behavior.

- [ ] **Rule 3: Do not reduce artifact richness to reduce calls**

If a stage requires more calls because it is split into smaller reliable units, accept that cost. The design goal is high-quality artifacts with recoverable failures, not fewer calls.

- [ ] **Rule 4: Commit each phase separately**

Each phase should end with a focused verification command and a commit whose body records “主要改动” and “验证结果”.

## Cross-Phase Contract

Phase 1 adds character quality fields:

```yaml
quality_counts:
  full: 0
  enriched: 0
  partial: 0
  fallback: 0
repair_counts:
  attempted: 0
  succeeded: 0
  failed: 0
```

Phase 2 adds worldbuilding quality fields:

```yaml
dimension_status:
  organizations: llm_verified
  locations: stats_seeded
  rules: llm_repaired
  resources: missing
source_quality_counts:
  llm_verified: 0
  llm_repaired: 0
  stats_seeded: 0
  missing: 0
```

Phase 3 consumes both to build:

```yaml
work_profile:
  quality_level: full | limited
insight_quality:
  expected: 0
  succeeded: 0
  repaired: 0
  failed: 0
release_gate:
  next_actions:
    - repair characters core biographies
    - repair worldbuilding organizations
```

## Completion Definition

The resilient enrichment effort is complete when:

- `characters` no longer drops valid profiles because another profile in the same batch failed.
- `worldbuilding` no longer becomes globally empty because one giant call timed out.
- `profile` can generate a limited but explicit work profile when upstream artifacts are partial.
- `insights` preserves successful chapters and repairs failed chapters individually.
- `release_gate` explains the smallest quality-restoring rerun path.
- Authorized verification on `nm_novel_20260701_7u96` shows improved quality distribution without manual YAML edits.
