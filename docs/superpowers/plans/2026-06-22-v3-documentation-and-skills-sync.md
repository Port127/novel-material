# Novel Material V3 文档与 Skills 同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将包版本正式升级为 3.0.0，收敛 V3 权威文档，并建立 `.agents/skills` 到 `.claude/skills` 的可重复同步与一致性检查。

**Architecture:** `.agents/skills` 是 Skills 唯一事实来源，平台相关说明改为同时覆盖 Claude 与 Codex 的中立正文，同步脚本负责生成 `.claude/skills` 镜像。现行文档按入口、产品、架构、操作、Agent 规则分工；题材感知独立指南的有效内容合并后删除。确定性测试检查版本、链接、CLI 声明和双目录一致性。

**Tech Stack:** Python 3.10+、Typer CLI、Markdown、`pathlib`、`shutil`、pytest、Git。

---

## 文件结构与职责

### 新建文件

- `scripts/sync_agent_skills.py`：从 `.agents/skills` 同步受管文件到 `.claude/skills`，支持 `--check`。
- `tests/scripts/test_sync_agent_skills.py`：同步、漂移、隐藏文件和多余受管文件测试。
- `scripts/check_v3_docs.py`：检查 V3 版本、现行链接、Agent 指南和公开 CLI 声明。
- `tests/scripts/test_check_v3_docs.py`：文档一致性规则测试。

### 修改或删除文件

- `pyproject.toml`：包版本升级到 `3.0.0`。
- `.agents/skills/{my-create-skill,plan-first,skill-discovery}/SKILL.md`：平台中立化。
- `.claude/skills/**`：由同步脚本生成镜像。
- `README.md`、`docs/REQUIREMENTS.md`、`ARCHITECTURE.md`、`docs/USER_MANUAL.md`、`AGENTS.md`、`CLAUDE.md`、`docs/README.md`：V3 权威文档。
- `docs/GENRE_AWARE_ANALYSIS.md`：有效内容合并后删除。
- `src/novel_material/storage/schema.sql`：只更新项目代际注释，不修改数据库 schema。

---

### Task 1：建立 Skills 同步器的失败测试

**Files:**
- Create: `tests/scripts/test_sync_agent_skills.py`
- Create: `scripts/sync_agent_skills.py`

- [ ] **Step 1: 编写同步与校验失败测试**

```python
from pathlib import Path

from scripts.sync_agent_skills import check_skills, sync_skills


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_reports_drift_and_sync_repairs_it(tmp_path):
    source = tmp_path / ".agents" / "skills"
    target = tmp_path / ".claude" / "skills"
    write(source / "demo" / "SKILL.md", "source\n")
    write(target / "demo" / "SKILL.md", "stale\n")

    assert check_skills(source, target) == ["内容不同: demo/SKILL.md"]
    sync_skills(source, target)
    assert check_skills(source, target) == []
    assert (target / "demo" / "SKILL.md").read_text() == "source\n"


def test_hidden_files_are_not_managed(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(source / "demo" / "SKILL.md", "same\n")
    write(target / "demo" / "SKILL.md", "same\n")
    write(target / ".DS_Store", "local")
    assert check_skills(source, target) == []
```

- [ ] **Step 2: 运行测试并确认因模块缺失而失败**

Run: `python -m pytest tests/scripts/test_sync_agent_skills.py -v`

Expected: FAIL，提示 `scripts.sync_agent_skills` 不存在。

- [ ] **Step 3: 实现最小同步器**

```python
def managed_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(root).parts)
    }


def check_skills(source: Path, target: Path) -> list[str]:
    source_files = managed_files(source)
    target_files = managed_files(target)
    issues = [f"目标缺失: {name}" for name in sorted(source_files.keys() - target_files.keys())]
    issues += [f"目标多余: {name}" for name in sorted(target_files.keys() - source_files.keys())]
    issues += [
        f"内容不同: {name}"
        for name in sorted(source_files.keys() & target_files.keys())
        if source_files[name].read_bytes() != target_files[name].read_bytes()
    ]
    return issues


def sync_skills(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Skills 源目录不存在: {source}")
    for name, source_path in managed_files(source).items():
        target_path = target / name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    for name, target_path in managed_files(target).items():
        if name not in managed_files(source):
            target_path.unlink()
```

CLI 使用 `--source`、`--target` 和 `--check`；`--check` 有问题时逐行输出并退出 1。

- [ ] **Step 4: 运行同步器测试**

Run: `python -m pytest tests/scripts/test_sync_agent_skills.py -v`

Expected: PASS。

- [ ] **Step 5: 提交同步器**

```bash
git add scripts/sync_agent_skills.py tests/scripts/test_sync_agent_skills.py
git commit -m "skills(sync): 建立双目录同步与校验" -m $'主要改动：\n- 增加 .agents 到 .claude 的受管文件同步器。\n- 增加只读校验、漂移和隐藏文件测试。\n\n验证结果：\n- python -m pytest tests/scripts/test_sync_agent_skills.py -v：通过。'
```

### Task 2：平台中立化并同步全部 Skills

**Files:**
- Modify: `.agents/skills/my-create-skill/SKILL.md`
- Modify: `.agents/skills/plan-first/SKILL.md`
- Modify: `.agents/skills/skill-discovery/SKILL.md`
- Modify: `.claude/skills/**`

- [ ] **Step 1: 运行仓库检查并确认当前失败**

Run: `python scripts/sync_agent_skills.py --check`

Expected: FAIL，至少报告 `nm-search/SKILL.md` 和三个平台差异 Skill。

- [ ] **Step 2: 平台中立化源 Skills**

具体规则：

- `my-create-skill` 同时列出 Codex 的 `.agents/skills`、`~/.codex/skills` 与 Claude 的 `.claude/skills`、`~/.claude/skills`。
- `plan-first` 使用“宿主工具内置 Plan 模式”，不绑定 Claude 或 Codex。
- `skill-discovery` 同时列出 Claude JSONL、Codex history 和 Cursor transcript；现有 Skill 扫描同时覆盖 `.agents/skills` 与 `.claude/skills`。
- 删除所有错误的 `.Codex` 大写路径。

- [ ] **Step 3: 执行同步并校验**

Run: `python scripts/sync_agent_skills.py && python scripts/sync_agent_skills.py --check`

Expected: 同步命令成功；检查命令退出 0 且无漂移。

- [ ] **Step 4: 提交 Skills 镜像**

```bash
git add .agents/skills .claude/skills
git commit -m "skills(sync): 统一 Claude 与 Codex 项目技能" -m $'主要改动：\n- 将平台路径说明改为同时支持 Claude 与 Codex。\n- 从 .agents/skills 生成 .claude/skills 镜像。\n\n验证结果：\n- python scripts/sync_agent_skills.py --check：通过。'
```

### Task 3：建立 V3 文档一致性检查

**Files:**
- Create: `tests/scripts/test_check_v3_docs.py`
- Create: `scripts/check_v3_docs.py`

- [ ] **Step 1: 编写版本、链接和 Agent 指南测试**

```python
from pathlib import Path

from scripts.check_v3_docs import check_current_docs


def test_check_rejects_v2_and_deleted_guide_links(tmp_path):
    (tmp_path / "README.md").write_text("# Novel Material V2\n[旧](docs/GENRE_AWARE_ANALYSIS.md)")
    issues = check_current_docs(tmp_path, [Path("README.md")])
    assert any("V2" in issue for issue in issues)
    assert any("GENRE_AWARE_ANALYSIS" in issue for issue in issues)


def test_check_accepts_v3_document(tmp_path):
    (tmp_path / "README.md").write_text("# Novel Material V3\n")
    assert check_current_docs(tmp_path, [Path("README.md")]) == []
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/scripts/test_check_v3_docs.py -v`

Expected: FAIL，提示 `scripts.check_v3_docs` 不存在。

- [ ] **Step 3: 实现检查器**

检查器接受项目根目录和现行文档列表，报告：`Novel Material V2`、`version = "2.0.0"`、`GENRE_AWARE_ANALYSIS.md` 链接、过期搜索描述、缺失的 Markdown 相对链接。另提供 `normalize_agent_guide()`，只把 `.agents/skills` 与 `.claude/skills` 归一为 `{skills_dir}` 后比较 `AGENTS.md` 与 `CLAUDE.md`。

```python
FORBIDDEN = {
    "Novel Material V2": "仍包含 V2 项目标识",
    'version = "2.0.0"': "仍包含 2.0.0 包版本",
    "GENRE_AWARE_ANALYSIS.md": "仍链接已合并的题材分析指南",
}


def check_current_docs(root: Path, documents: list[Path]) -> list[str]:
    issues: list[str] = []
    for relative in documents:
        text = (root / relative).read_text(encoding="utf-8")
        for pattern, message in FORBIDDEN.items():
            if pattern in text:
                issues.append(f"{relative}: {message}")
    return issues


def normalize_agent_guide(text: str) -> str:
    return text.replace(".agents/skills", "{skills_dir}").replace(
        ".claude/skills", "{skills_dir}"
    )
```

- [ ] **Step 4: 运行检查器测试**

Run: `python -m pytest tests/scripts/test_check_v3_docs.py -v`

Expected: PASS。

- [ ] **Step 5: 提交文档检查器**

```bash
git add scripts/check_v3_docs.py tests/scripts/test_check_v3_docs.py
git commit -m "test(docs): 建立 V3 文档一致性检查" -m $'主要改动：\n- 检查现行文档版本、删除链接和过期能力描述。\n- 规范化比较 AGENTS 与 CLAUDE 指南。\n\n验证结果：\n- python -m pytest tests/scripts/test_check_v3_docs.py -v：通过。'
```

### Task 4：正式升级 V3 并更新入口与产品文档

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `docs/REQUIREMENTS.md`
- Modify: `src/novel_material/storage/schema.sql`

- [ ] **Step 1: 运行 V3 检查并确认版本失败**

Run: `python scripts/check_v3_docs.py`

Expected: FAIL，报告包版本和现行文档仍含 V2。

- [ ] **Step 2: 更新版本与 README**

- `pyproject.toml` 改为 `version = "3.0.0"`。
- README 标题和定位改为 V3。
- 当前能力列出 `chapter/event/outline/character/world/detail/insight` 七类检索、评测和迁移。
- 删除单路关键词检索的过期限制，保留人工基线、真实容量实测和默认 LLM 重排尚未完成的边界。

- [ ] **Step 3: 收敛需求文档**

保留用户场景、六项核心检索需求、质量门禁、规模目标和不做内容；删除与架构或手册重复的命令、模块路径和实现过程。文首代际改为 V3。

- [ ] **Step 4: 更新 schema 文件头注释**

只将 `-- Novel Material V2 - PostgreSQL Schema` 改为 V3，不修改任何 DDL。

- [ ] **Step 5: 运行版本检查和测试**

Run: `python -c 'from pathlib import Path; assert "2.0.0" not in Path("pyproject.toml").read_text(); assert "Novel Material V2" not in Path("README.md").read_text()' && python -m pytest -q`

Expected: 版本与入口断言通过；单元测试全部通过。完整文档检查留到 Task 6，因为架构、手册和 Agent 指南将在后续任务更新。

- [ ] **Step 6: 提交 V3 入口与需求**

```bash
git add pyproject.toml README.md docs/REQUIREMENTS.md src/novel_material/storage/schema.sql
git commit -m "docs(v3): 升级项目版本与产品文档" -m $'主要改动：\n- 包版本升级为 3.0.0。\n- 更新 V3 入口、产品边界和质量限制。\n\n验证结果：\n- 文档一致性阶段检查已通过版本与入口项。\n- python -m pytest -q：通过。'
```

### Task 5：合并题材感知指南并更新架构与手册

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `docs/USER_MANUAL.md`
- Delete: `docs/GENRE_AWARE_ANALYSIS.md`

- [ ] **Step 1: 建立独有事实清单**

从待删除文档逐项确认并记录到目标章节：`common + 题材 profile`、profile 列表、`chapter_insights/{chapter}.yaml`、fast/standard/deep 行为、显式 `--profile`、validate/search 命令、批次与单次修复边界。

- [ ] **Step 2: 更新架构**

将 L1/L2、profile resolver、输出契约、evidence/confidence、扩展 profile 约束写入架构；同步 V3 目录、质量检索服务、迁移和已知限制。

- [ ] **Step 3: 更新用户手册**

将 insights CLI、运行模式、配置、校验、搜索和失败处理写入手册；以 `python -m novel_material.cli.main ... --help` 验证命令，不硬编码服务商模型。

- [ ] **Step 4: 删除独立指南并扫描链接**

Run: `git rm docs/GENRE_AWARE_ANALYSIS.md && rg -n "GENRE_AWARE_ANALYSIS" README.md ARCHITECTURE.md AGENTS.md CLAUDE.md docs`

Expected: `rg` 无匹配。

- [ ] **Step 5: 运行帮助与文档检查**

Run: `python -m novel_material.cli.main pipeline insights --help && python -m novel_material.cli.main search insight --help && python -m novel_material.cli.main validate insights --help && python scripts/check_v3_docs.py`

Expected: 三个帮助命令退出 0；架构、手册和已删除链接检查通过。

- [ ] **Step 6: 提交架构和手册**

```bash
git add ARCHITECTURE.md docs/USER_MANUAL.md docs/GENRE_AWARE_ANALYSIS.md
git commit -m "docs(v3): 合并题材分析并更新架构手册" -m $'主要改动：\n- 将题材感知分析的有效内容并入架构与用户手册。\n- 删除重复的独立功能指南。\n\n验证结果：\n- insights 相关 CLI 帮助均通过。\n- 删除链接扫描无匹配。'
```

### Task 6：同步 Agent 指南和文档索引

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `docs/README.md`

- [ ] **Step 1: 更新 AGENTS 事实来源**

改为 V3，记录 `.agents/skills` 是 Skills 事实来源、`.claude/skills` 是生成镜像；保留中文沟通、提交格式、CLI 优先、YAML 事实来源、同步副作用和搜索质量边界。

- [ ] **Step 2: 生成 CLAUDE 指南**

以 AGENTS 正文为基础，仅将项目 Skill 入口 `.agents/skills` 改为 `.claude/skills`。搜索命令、风险、状态和配置说明必须相同。

- [ ] **Step 3: 更新文档索引**

删除题材感知指南入口；列出 V3 权威文档、检索容量状态、历史工作记录和两项待办：人工相关性标注、真实百万级容量执行器与实测。

- [ ] **Step 4: 运行指南和 Skills 校验**

Run: `python scripts/check_v3_docs.py && python scripts/sync_agent_skills.py --check`

Expected: 两个命令均退出 0。

- [ ] **Step 5: 提交 Agent 指南**

```bash
git add AGENTS.md CLAUDE.md docs/README.md
git commit -m "docs(v3): 统一 Agent 指南与文档索引" -m $'主要改动：\n- 同步 Claude 与 Codex 的 V3 操作规则。\n- 更新现行文档索引和明确待办。\n\n验证结果：\n- V3 文档检查与 Skills 同步检查均通过。'
```

### Task 7：最终回归与工作区边界验收

**Files:**
- Modify only if verification reveals a scoped defect in Tasks 1-6.

- [ ] **Step 1: 运行同步与文档专项测试**

Run: `python -m pytest tests/scripts/test_sync_agent_skills.py tests/scripts/test_check_v3_docs.py -v`

Expected: PASS。

- [ ] **Step 2: 运行完整单元测试**

Run: `python -m pytest -q`

Expected: 全部通过，skip 数不高于执行前基线。

- [ ] **Step 3: 运行真实 CLI 帮助冒烟**

Run: `python -m novel_material.cli.main --help && python -m novel_material.cli.main pipeline --help && python -m novel_material.cli.main search --help && python -m novel_material.cli.main eval --help && python -m novel_material.cli.main storage --help && python -m novel_material.cli.main validate --help`

Expected: 全部退出 0，公开命令与手册一致。

- [ ] **Step 4: 执行最终静态检查**

Run: `python scripts/sync_agent_skills.py --check && python scripts/check_v3_docs.py && git diff --check`

Expected: 全部退出 0。

- [ ] **Step 5: 检查用户文件边界**

Run: `git status --short && git diff -- docs/feedback.md config/providers.yaml`

Expected: `docs/feedback.md` 保留用户原改动；`config/providers.yaml` 无本任务改动；`eval/search_candidates.yaml` 不进入暂存区。

- [ ] **Step 6: 仅在验证修复产生新改动时提交**

提交正文必须逐项记录修复内容和完整验证结果；若没有新改动，不创建空提交。
