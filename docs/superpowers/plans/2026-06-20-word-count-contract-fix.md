# Word Count Contract Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the stale chapter word-count test, verify the complete feature branch, merge it into `main`, and remove its owned worktree.

**Architecture:** Keep ingestion behavior unchanged because chapter-level and novel-level counts already share the non-whitespace-character contract. Correct only the test expectation, then use Git's normal worktree merge and cleanup sequence while preserving the unrelated `config/providers.yaml` modification in the main workspace.

**Tech Stack:** Python 3.12, pytest, Git worktrees

---

### Task 1: Correct the stale word-count test

**Files:**
- Modify: `tests/pipeline/test_ingest.py:101-112`
- Reference: `src/novel_material/pipeline/ingest.py:117-143`

- [x] **Step 1: Verify the existing test fails for the contract mismatch**

Run:

```bash
python -m pytest tests/pipeline/test_ingest.py::TestChapterSplit::test_word_count -q
```

Expected: FAIL because the current test expects `14` while `split_chapters()` returns `13` after removing the title space and newline.

- [x] **Step 2: Correct the test expectation**

Replace the final comment, setup, and assertion with:

```python
        # word_count 包含标题+内容，但不含空格、换行等空白字符
        full_content = "第1章 开篇\n这是一段测试内容"
        assert chapters[0]["word_count"] == len(re.sub(r"\s", "", full_content))
```

Add the standard-library import at the top of the test module:

```python
import re
```

- [x] **Step 3: Verify the corrected focused test passes**

Run:

```bash
python -m pytest tests/pipeline/test_ingest.py::TestChapterSplit::test_word_count -q
```

Expected: `1 passed`.

- [x] **Step 4: Verify the complete feature branch**

Run:

```bash
python -m pytest
```

Expected: `73 passed, 1 skipped` with exit code 0.

### Task 2: Commit the verified feature branch

**Files:**
- Modify: all tracked and untracked feature files currently present in `.worktrees/genre-aware-analysis-profiles`

- [ ] **Step 1: Review repository state and whitespace errors**

Run:

```bash
git status --short
git diff --check
```

Expected: only the genre-aware analysis work, its documentation, and the corrected word-count test are listed; `git diff --check` exits 0.

- [ ] **Step 2: Commit the feature changes**

Run:

```bash
git add -A
git commit -m "feat: add genre-aware analysis profiles"
```

Expected: one new commit on `codex-genre-aware-analysis-profiles`; the worktree becomes clean.

### Task 3: Merge and verify `main`

**Files:**
- Preserve: `config/providers.yaml` in the main workspace

- [ ] **Step 1: Merge the feature branch into `main`**

Run from the main workspace:

```bash
git merge codex-genre-aware-analysis-profiles
```

Expected: a successful fast-forward or merge without touching the unrelated working-tree modification in `config/providers.yaml`.

- [ ] **Step 2: Verify the merged result**

Run:

```bash
python -m pytest
```

Expected: `73 passed, 1 skipped` with exit code 0.

### Task 4: Remove the owned worktree and branch

**Files:**
- Remove: `.worktrees/genre-aware-analysis-profiles`
- Remove if empty: `.worktrees`

- [ ] **Step 1: Remove the registered worktree and prune metadata**

Run from the main workspace:

```bash
git worktree remove .worktrees/genre-aware-analysis-profiles
git worktree prune
```

Expected: the feature worktree is absent from `git worktree list`.

- [ ] **Step 2: Delete the merged feature branch**

Run:

```bash
git branch -d codex-genre-aware-analysis-profiles
```

Expected: Git confirms deletion because the branch is fully merged.

- [ ] **Step 3: Remove the empty container directory and verify final state**

Run:

```bash
rmdir .worktrees
git status --short --branch
git worktree list
```

Expected: `.worktrees` no longer exists, only the main worktree is registered, and the preserved `config/providers.yaml` modification remains visible.
