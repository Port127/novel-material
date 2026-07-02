# 项目文档物理归档 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目文档整理为“事实源、当前工作、历史归档、非项目文档”四层，并把已历史化文档物理移动到 `docs/archive/`。

**Architecture:** 保留顶层和 `docs/` 根部作为事实源与当前工作入口；把审查、复盘、已解决反馈和历史 Superpowers 记录移动到 `docs/archive/`；只通过 `docs/README.md` 暴露维护导航。实施时保护当前工作树中已有的 `docs/feedback.md` 修改和未跟踪 `docs/analysis/`，避免把非本轮内容混进提交。

**Tech Stack:** Markdown 文档、Git 文件移动、`scripts/check_v3_docs.py` 文档一致性检查、`python -m novel_material.cli.main <group> --help` CLI 事实核对。

---

## File Structure

**Create:**
- `docs/archive/README.md`：归档区入口和历史链接说明。
- `docs/current/plans/README.md`：当前计划目录说明。

**Move:**
- `docs/code-review-report.md` -> `docs/archive/reviews/code-review-report.md`
- `docs/code-review-llm-response-contract-report.md` -> `docs/archive/reviews/code-review-llm-response-contract-report.md`
- `docs/feedback/archive/*.md` -> `docs/archive/feedback/*.md`
- `docs/analysis/*.md` -> `docs/archive/analysis/*.md`
- `docs/superpowers/execution/*` -> `docs/archive/superpowers/execution/*`
- `docs/superpowers/plans/2026-06-*.md` and `docs/superpowers/plans/2026-07-01-unattended-pipeline-quality-gate.md` -> `docs/archive/superpowers/plans/`
- `docs/superpowers/specs/2026-06-*.md` and `docs/superpowers/specs/2026-07-01-unattended-pipeline-quality-gate-design.md` -> `docs/archive/superpowers/specs/`

**Keep in place:**
- `docs/superpowers/specs/2026-07-02-documentation-archive-design.md`
- `docs/superpowers/plans/2026-07-02-documentation-archive.md`
- `README.md`
- `ARCHITECTURE.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/README.md`
- `docs/REQUIREMENTS.md`
- `docs/USER_MANUAL.md`
- `docs/search-benchmark.md`
- `docs/feedback.md`

**Modify:**
- `docs/README.md`：重写为事实源、当前工作、历史归档、非项目文档四类导航。
- `AGENTS.md`：补齐 CLI 速览中的 `profile`、`report`、`storage migrate`、`validate artifacts`。
- `CLAUDE.md`：与 `AGENTS.md` 保持同等 CLI 速览，只保留 Skill 入口路径差异。

---

### Task 1: Worktree Guard And Inventory

**Files:**
- Read: `docs/superpowers/specs/2026-07-02-documentation-archive-design.md`
- Read: `docs/README.md`
- Read: `AGENTS.md`
- Read: `CLAUDE.md`
- Read: `scripts/check_v3_docs.py`

- [ ] **Step 1: Confirm current worktree state**

Run:

```bash
git status --short
```

Expected at plan time:

```text
 M docs/feedback.md
?? docs/analysis/
```

If additional paths appear, record them in the task notes and do not stage them unless they are created or moved by this plan.

- [ ] **Step 2: Confirm `docs/analysis/` is not tracked**

Run:

```bash
git ls-files docs/analysis
```

Expected: no output. Treat `docs/analysis/` as existing user workspace content; move it physically to `docs/archive/analysis/`, but do not include those files in a commit unless the user explicitly approves tracking them.

- [ ] **Step 3: Capture the pre-change document inventory**

Run:

```bash
find docs -maxdepth 3 -type f -name '*.md' | sort
```

Expected: output includes `docs/code-review-report.md`, `docs/code-review-llm-response-contract-report.md`, `docs/feedback/archive/*.md`, `docs/superpowers/plans/*.md`, `docs/superpowers/specs/*.md`, and `docs/superpowers/execution/*/*.md`.

- [ ] **Step 4: Confirm current CLI facts before editing Agent guides**

Run:

```bash
python -m novel_material.cli.main pipeline --help
python -m novel_material.cli.main storage --help
python -m novel_material.cli.main validate --help
```

Expected:
- `pipeline` lists `profile` and `report`.
- `storage` lists `migrate`.
- `validate` lists `artifacts`.

---

### Task 2: Create Archive Entrypoints

**Files:**
- Create: `docs/archive/README.md`
- Create: `docs/current/plans/README.md`

- [ ] **Step 1: Create archive and current directories**

Run:

```bash
mkdir -p docs/archive/reviews docs/archive/analysis docs/archive/feedback docs/archive/superpowers/plans docs/archive/superpowers/specs docs/archive/superpowers/execution docs/current/plans
```

Expected: command exits `0`.

- [ ] **Step 2: Add `docs/archive/README.md`**

Create `docs/archive/README.md` with this exact content:

```markdown
# 历史归档

本目录保存已经历史化的审查报告、事故复盘、已解决反馈和 Superpowers 过程记录。归档文档默认不维护，只作为追溯证据。

## 目录

- `reviews/`：历史代码审查和定向审查报告。
- `analysis/`：事故复盘和深度分析记录。
- `feedback/`：已解决反馈归档。
- `superpowers/`：已完成或历史化的设计规格、实施计划和执行记录。

## 链接说明

归档执行会优先修复现行事实源和当前工作文档中的链接。历史文档内部可能保留归档前路径；遇到旧路径时，先在本目录下查找对应文件。
```

- [ ] **Step 3: Add `docs/current/plans/README.md`**

Create `docs/current/plans/README.md` with this exact content:

```markdown
# 当前计划

本目录只放仍在执行或即将执行的计划。已完成、废弃或仅供追溯的计划应移动到 `docs/archive/superpowers/plans/`。
```

- [ ] **Step 4: Stage only the new entrypoint docs**

Run:

```bash
git add docs/archive/README.md docs/current/plans/README.md
git diff --cached -- docs/archive/README.md docs/current/plans/README.md
```

Expected: cached diff only contains the two new README files.

---

### Task 3: Move Historical Documents

**Files:**
- Move: `docs/code-review-report.md`
- Move: `docs/code-review-llm-response-contract-report.md`
- Move: `docs/feedback/archive/*.md`
- Move: `docs/analysis/*.md`
- Move: `docs/superpowers/execution/*`
- Move: selected historical files in `docs/superpowers/plans/`
- Move: selected historical files in `docs/superpowers/specs/`

- [ ] **Step 1: Move review reports with Git history**

Run:

```bash
git mv docs/code-review-report.md docs/archive/reviews/code-review-report.md
git mv docs/code-review-llm-response-contract-report.md docs/archive/reviews/code-review-llm-response-contract-report.md
```

Expected: both files appear as renames in `git status --short`.

- [ ] **Step 2: Move resolved feedback archive with Git history**

Run:

```bash
git mv docs/feedback/archive/01-progress.md docs/archive/feedback/01-progress.md
git mv docs/feedback/archive/02-logging.md docs/archive/feedback/02-logging.md
git mv docs/feedback/archive/03-pipeline.md docs/archive/feedback/03-pipeline.md
git mv docs/feedback/archive/04-llm.md docs/archive/feedback/04-llm.md
git mv docs/feedback/archive/05-tags.md docs/archive/feedback/05-tags.md
git mv docs/feedback/archive/06-config.md docs/archive/feedback/06-config.md
git mv docs/feedback/archive/07-misc.md docs/archive/feedback/07-misc.md
rmdir docs/feedback/archive
```

Expected: `docs/feedback/archive` is removed if empty; `docs/feedback.md` remains in place and is not staged by this step.

- [ ] **Step 3: Move untracked analysis files physically**

Run:

```bash
mv docs/analysis/20260701_unattended_pipeline_failure_deep_analysis.md docs/archive/analysis/20260701_unattended_pipeline_failure_deep_analysis.md
mv docs/analysis/nm_novel_20260701_18cb_postmortem.md docs/archive/analysis/nm_novel_20260701_18cb_postmortem.md
mv docs/analysis/nm_novel_20260701_7u96_postmortem.md docs/archive/analysis/nm_novel_20260701_7u96_postmortem.md
rmdir docs/analysis
```

Expected: the files move under `docs/archive/analysis/`. Because these files were untracked at plan time, leave them untracked after moving unless the user approves staging them.

- [ ] **Step 4: Move historical Superpowers execution records**

Run:

```bash
git mv docs/superpowers/execution/2026-06-23-artifact-audit-report docs/archive/superpowers/execution/2026-06-23-artifact-audit-report
git mv docs/superpowers/execution/2026-06-29-global-navigation-and-character-biographies docs/archive/superpowers/execution/2026-06-29-global-navigation-and-character-biographies
git mv docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile docs/archive/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile
```

Expected: all three execution directories appear as renames under `docs/archive/superpowers/execution/`.

- [ ] **Step 5: Move historical Superpowers plans**

Run:

```bash
git mv docs/superpowers/plans/2026-06-20-documentation-consolidation.md docs/archive/superpowers/plans/2026-06-20-documentation-consolidation.md
git mv docs/superpowers/plans/2026-06-20-quality-first-retrieval.md docs/archive/superpowers/plans/2026-06-20-quality-first-retrieval.md
git mv docs/superpowers/plans/2026-06-21-chinese-language-and-commit-rules.md docs/archive/superpowers/plans/2026-06-21-chinese-language-and-commit-rules.md
git mv docs/superpowers/plans/2026-06-21-search-candidate-backfill.md docs/archive/superpowers/plans/2026-06-21-search-candidate-backfill.md
git mv docs/superpowers/plans/2026-06-22-runtime-observability-and-cli-correctness.md docs/archive/superpowers/plans/2026-06-22-runtime-observability-and-cli-correctness.md
git mv docs/superpowers/plans/2026-06-22-v3-documentation-and-skills-sync.md docs/archive/superpowers/plans/2026-06-22-v3-documentation-and-skills-sync.md
git mv docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md docs/archive/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
git mv docs/superpowers/plans/2026-06-23-standard-insights-chapter-limit.md docs/archive/superpowers/plans/2026-06-23-standard-insights-chapter-limit.md
git mv docs/superpowers/plans/2026-06-24-llm-response-contract-hardening.md docs/archive/superpowers/plans/2026-06-24-llm-response-contract-hardening.md
git mv docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md docs/archive/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
git mv docs/superpowers/plans/2026-06-30-layered-worldbuilding-and-work-profile.md docs/archive/superpowers/plans/2026-06-30-layered-worldbuilding-and-work-profile.md
git mv docs/superpowers/plans/2026-07-01-unattended-pipeline-quality-gate.md docs/archive/superpowers/plans/2026-07-01-unattended-pipeline-quality-gate.md
```

Expected: `docs/superpowers/plans/2026-07-02-documentation-archive.md` remains in place.

- [ ] **Step 6: Move historical Superpowers specs**

Run:

```bash
git mv docs/superpowers/specs/2026-06-20-documentation-consolidation-design.md docs/archive/superpowers/specs/2026-06-20-documentation-consolidation-design.md
git mv docs/superpowers/specs/2026-06-20-quality-first-retrieval-design.md docs/archive/superpowers/specs/2026-06-20-quality-first-retrieval-design.md
git mv docs/superpowers/specs/2026-06-21-chinese-language-and-commit-rules-design.md docs/archive/superpowers/specs/2026-06-21-chinese-language-and-commit-rules-design.md
git mv docs/superpowers/specs/2026-06-21-search-candidate-backfill-design.md docs/archive/superpowers/specs/2026-06-21-search-candidate-backfill-design.md
git mv docs/superpowers/specs/2026-06-22-agent-claude-skills-sync-design.md docs/archive/superpowers/specs/2026-06-22-agent-claude-skills-sync-design.md
git mv docs/superpowers/specs/2026-06-22-runtime-observability-and-cli-correctness-design.md docs/archive/superpowers/specs/2026-06-22-runtime-observability-and-cli-correctness-design.md
git mv docs/superpowers/specs/2026-06-22-v3-documentation-consolidation-design.md docs/archive/superpowers/specs/2026-06-22-v3-documentation-consolidation-design.md
git mv docs/superpowers/specs/2026-06-23-layered-analysis-and-quality-report-design.md docs/archive/superpowers/specs/2026-06-23-layered-analysis-and-quality-report-design.md
git mv docs/superpowers/specs/2026-06-23-standard-insights-chapter-limit-design.md docs/archive/superpowers/specs/2026-06-23-standard-insights-chapter-limit-design.md
git mv docs/superpowers/specs/2026-06-24-llm-response-contract-hardening-design.md docs/archive/superpowers/specs/2026-06-24-llm-response-contract-hardening-design.md
git mv docs/superpowers/specs/2026-06-30-layered-worldbuilding-and-work-profile-design.md docs/archive/superpowers/specs/2026-06-30-layered-worldbuilding-and-work-profile-design.md
git mv docs/superpowers/specs/2026-07-01-unattended-pipeline-quality-gate-design.md docs/archive/superpowers/specs/2026-07-01-unattended-pipeline-quality-gate-design.md
```

Expected: `docs/superpowers/specs/2026-07-02-documentation-archive-design.md` remains in place.

- [ ] **Step 7: Verify only current Superpowers files remain active**

Run:

```bash
find docs/superpowers -maxdepth 3 -type f -name '*.md' | sort
```

Expected:

```text
docs/superpowers/plans/2026-07-02-documentation-archive.md
docs/superpowers/specs/2026-07-02-documentation-archive-design.md
```

---

### Task 4: Rewrite Documentation Index

**Files:**
- Modify: `docs/README.md`

- [ ] **Step 1: Replace `docs/README.md` with the new navigation**

Replace the full file with this exact content:

```markdown
# 项目文档

本目录是 Novel Material V3 的项目文档入口。文档分为事实源、当前工作、历史归档和非项目文档四类；历史归档只用于追溯，不参与当前需求、架构或操作规范裁决。

## 事实源

| 文档 | 维护状态 | 用途 |
|---|---|---|
| [README](../README.md) | 现行入口 | 项目简介、当前能力与快速开始 |
| [项目需求](REQUIREMENTS.md) | 产品事实源 | 产品边界、质量目标、规模与不做什么 |
| [系统架构](../ARCHITECTURE.md) | 技术事实源 | 当前架构、数据流、模块边界与已知限制 |
| [用户手册](USER_MANUAL.md) | 使用事实源 | 与真实 CLI 一致的安装、命令和故障排查 |
| [Agent 指南](../AGENTS.md) | Agent 规则 | Codex 与通用 Agent 的项目操作规范 |
| [Claude 指南](../CLAUDE.md) | Agent 规则 | Claude Code 的项目操作规范 |

文档发生冲突时，依次以用户当前请求、Agent 指南、项目需求、系统架构、用户手册、README 为准。归档文档仅供追溯，不参与裁决。

## 当前工作

| 文档 | 维护状态 | 用途 |
|---|---|---|
| [检索容量与质量门禁](search-benchmark.md) | 当前实验状态 | 容量计划、ANN 准入条件与未执行项 |
| [未解决反馈](feedback.md) | 当前待办池 | 仍需处理的问题和想法 |
| [当前计划](current/plans/) | 当前计划 | 仍在执行或即将执行的计划 |

运行报告、前置导航、人物完整小传、分层世界观和作品画像能够说明流水线是否完整、资源消耗、产物规则问题和作品级结构入口，并让素材结构更完整，但不能替代检索质量评测。Golden Query 人工标注缺口仍然有效。

## 历史归档

| 目录 | 用途 |
|---|---|
| [归档说明](archive/README.md) | 归档区入口和历史链接说明 |
| [审查报告](archive/reviews/) | 历史代码审查和定向审查报告 |
| [事故复盘](archive/analysis/) | 事故分析和 postmortem |
| [已解决反馈](archive/feedback/) | 已完成反馈的历史记录 |
| [Superpowers 记录](archive/superpowers/) | 已完成或历史化的设计规格、实施计划和执行记录 |

归档文档默认不维护。历史计划、规格或执行记录与当前代码冲突时，以事实源文档和代码为准。

## 子系统契约

- [标签体系](../data/tag-system/README.md)：标签分类、维度和平台映射。
- [数据库迁移](../src/novel_material/storage/migrations/README.md)：已有数据库迁移顺序。

## 非项目文档

以下路径不纳入项目文档维护体系：

- `material/`：小说素材和语料。
- `data/`：运行数据、事实产物和可重建查询数据。
- `.pytest_cache/`：测试工具缓存。
- `*.egg-info/`：构建元数据。

## Skills

项目 Skills 以 `.agents/skills/` 为事实来源，`.claude/skills/` 为生成镜像；运行 `python scripts/sync_agent_skills.py --check` 可检查漂移。

## 建议阅读顺序

- 普通使用者：README -> 用户手册。
- 开发者：项目需求 -> 系统架构 -> 用户手册。
- Agent：AGENTS 或 CLAUDE -> 项目需求 -> 用户手册。
```

- [ ] **Step 2: Confirm removed outdated work-record links**

Run:

```bash
rg -n "feedback/archive|superpowers/(plans|specs|execution)|code-review-report|analysis/" docs/README.md
```

Expected: matches only point to `archive/...` paths or no output.

---

### Task 5: Sync Agent CLI Summaries

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update Pipeline command blocks in both Agent guides**

In both `AGENTS.md` and `CLAUDE.md`, replace the Pipeline CLI block with:

```bash
nm pipeline ingest <file>
nm pipeline evaluate <id>
nm pipeline analyze <id> [--window] [--skip-embedding]
nm pipeline insights <id> [--start N] [--end N] [--profile NAME]
nm pipeline outline <id>
nm pipeline worldbuilding <id>
nm pipeline characters <id> [--repair-character NAME]
nm pipeline tags <id>
nm pipeline refine <id>
nm pipeline profile <id>
nm pipeline full <file> [--mode fast|standard|deep]
nm pipeline status <id>
nm pipeline continue <id> [--mode fast|standard|deep]
nm pipeline report <id> [--run-id RUN_ID]
```

- [ ] **Step 2: Update Storage and Validate command blocks in both Agent guides**

In both `AGENTS.md` and `CLAUDE.md`, replace the Storage 与 Validate block with:

```bash
nm storage migrate
nm storage init-db
nm storage init-data
nm storage init-tags
nm storage sync [material_id] [--provider NAME] [--window]

nm validate validate [material_id]
nm validate validate --all
nm validate quality <material_id> [--start N] [--end N]
nm validate insights <material_id>
nm validate artifacts <material_id> [--review]
```

- [ ] **Step 3: Confirm Agent guides differ only in allowed Skill path wording**

Run:

```bash
python scripts/check_v3_docs.py
```

Expected after Task 6 link fixes: exit `0`. If it fails at this step only because archive paths are not yet staged or docs links are mid-edit, continue to Task 6 and rerun.

---

### Task 6: Validate Links And Current Document Rules

**Files:**
- Read: `README.md`
- Read: `ARCHITECTURE.md`
- Read: `docs/REQUIREMENTS.md`
- Read: `docs/USER_MANUAL.md`
- Read: `docs/README.md`
- Read: `AGENTS.md`
- Read: `CLAUDE.md`

- [ ] **Step 1: Run the repository documentation checker**

Run:

```bash
python scripts/check_v3_docs.py
```

Expected: command exits `0` with no output.

- [ ] **Step 2: Check root and docs-level Markdown inventory**

Run:

```bash
find . -path './.git' -prune -o -path './data' -prune -o -path './material' -prune -o -path './*.egg-info' -prune -o -type f \( -name '*.md' -o -name '*.rst' -o -name '*.txt' -o -name '*.adoc' \) -print | sed 's#^\./##' | sort
```

Expected:
- Top-level facts remain: `README.md`, `ARCHITECTURE.md`, `AGENTS.md`, `CLAUDE.md`.
- `docs/` root keeps `README.md`, `REQUIREMENTS.md`, `USER_MANUAL.md`, `feedback.md`, `search-benchmark.md`.
- Historical review, feedback archive, analysis, and older Superpowers files are under `docs/archive/`.
- `material/` and `data/` do not appear in the output.

- [ ] **Step 3: Check stale references in current docs**

Run:

```bash
rg -n "docs/superpowers/(plans|specs|execution)|feedback/archive|docs/analysis|code-review-report|code-review-llm-response-contract-report" README.md docs/README.md docs/REQUIREMENTS.md ARCHITECTURE.md docs/USER_MANUAL.md AGENTS.md CLAUDE.md
```

Expected: no output, except intentional archive links in `docs/README.md` if the pattern is updated to include `archive/`.

- [ ] **Step 4: Check current Superpowers active files**

Run:

```bash
find docs/superpowers -maxdepth 3 -type f -name '*.md' | sort
```

Expected:

```text
docs/superpowers/plans/2026-07-02-documentation-archive.md
docs/superpowers/specs/2026-07-02-documentation-archive-design.md
```

- [ ] **Step 5: Check archive files exist**

Run:

```bash
find docs/archive -maxdepth 4 -type f -name '*.md' | sort
```

Expected: output includes `docs/archive/README.md`, both review reports, seven feedback archive files, historical Superpowers specs/plans/execution records, and any physically moved analysis files.

---

### Task 7: Stage And Commit Documentation Archive

**Files:**
- Stage: all files created, moved, or modified by Tasks 2-6
- Do not stage: unrelated pre-existing `docs/feedback.md` changes unless Task 4 intentionally edited it, which this plan does not require.
- Do not stage: `docs/archive/analysis/*.md` if they originated from untracked `docs/analysis/` and the user has not approved tracking them.

- [ ] **Step 1: Review unstaged and staged changes**

Run:

```bash
git status --short
git diff -- docs/README.md AGENTS.md CLAUDE.md docs/archive/README.md docs/current/plans/README.md
git diff --cached --stat
```

Expected:
- `docs/feedback.md` remains unstaged if it was a pre-existing user edit.
- Archive moves appear as renames.
- Current plan and design remain in `docs/superpowers/`.

- [ ] **Step 2: Stage intended tracked changes**

Run:

```bash
git add docs/README.md AGENTS.md CLAUDE.md docs/archive/README.md docs/current/plans/README.md docs/archive/reviews docs/archive/feedback docs/archive/superpowers docs/superpowers
```

Expected: intended edits and tracked renames are staged.

- [ ] **Step 3: Stage untracked analysis files only with approval**

If the user approves tracking moved analysis files, run:

```bash
git add docs/archive/analysis
```

Expected: `docs/archive/analysis/*.md` becomes staged. If the user does not approve tracking them, leave the files untracked in their archived location.

- [ ] **Step 4: Verify final staged set**

Run:

```bash
git diff --cached --name-status
```

Expected:
- Includes archive README, current plans README, docs index, Agent guide updates, and tracked file renames.
- Excludes unrelated `docs/feedback.md` user changes.

- [ ] **Step 5: Commit with project-format Chinese message**

Run:

```bash
git commit -m "docs: 归档历史项目文档" -m "背景与目的：
- 收敛项目文档维护面，将现行事实源、当前工作和历史记录分层管理。

主要改动：
- 将历史审查报告、已解决反馈和 Superpowers 历史记录移动到 docs/archive/。
- 新增归档入口和当前计划目录说明。
- 重写 docs/README.md，明确事实源、当前工作、历史归档和非项目文档边界。
- 校准 AGENTS.md 与 CLAUDE.md 的 CLI 速览，补齐 profile、report、storage migrate 和 validate artifacts。

影响范围：
- 文档路径发生变化，现行事实源和当前工作入口已更新。
- 历史归档默认不再维护，仅用于追溯。

验证结果：
- python scripts/check_v3_docs.py
- find/rg 检查确认历史文档已移动到 docs/archive/，material 和 data 未纳入项目文档体系。"
```

Expected: commit succeeds and only contains this plan的文档整理改动。

---

## Self-Review

- Spec coverage: Tasks 2-3 implement physical archive structure; Task 4 implements `docs/README.md` as unique navigation; Task 5 handles Agent CLI drift; Task 6 verifies links and non-project exclusions; Task 7 protects existing user changes during staging.
- Completeness scan: every task names exact paths, commands, expected results, and staging rules.
- Type and path consistency: all active paths use `docs/superpowers/...`; all historical paths use `docs/archive/...`; `docs/analysis/` is handled as untracked workspace content and not silently committed.
