# 项目文档物理归档设计

## 背景

当前项目文档同时包含事实源、使用说明、Agent 规则、审查报告、事故复盘、历史计划、执行记录和素材文本。直接按扩展名扫描会把 `material/` 下的大量小说文本、运行产物和历史记录混入项目文档，导致维护边界不清。

本次整理目标是通过物理归档收敛维护面：正式文档集中留在顶层与 `docs/` 根部，历史记录移动到 `docs/archive/`，仍在使用的工作文档保留可见入口。

## 目标

- 明确哪些文档是当前事实源，哪些只是历史记录。
- 让 `docs/README.md` 成为唯一文档导航入口。
- 将已历史化的审查、复盘、反馈归档和 Superpowers 记录移动到 `docs/archive/`。
- 保留仍需主动维护的当前工作文档。
- 避免移动素材、运行数据、缓存和生成元数据。

## 非目标

- 不重写需求、架构和用户手册的业务内容。
- 不整理 `material/` 小说素材和 `data/` 运行产物。
- 不手工维护 `.claude/skills/` 镜像内容。
- 不在本轮判断历史计划的技术正确性，只处理文档层级与导航。

## 归档方案

采用分层物理归档。

```text
docs/
├── README.md
├── REQUIREMENTS.md
├── USER_MANUAL.md
├── search-benchmark.md
├── feedback.md
├── current/
│   └── plans/
└── archive/
    ├── reviews/
    ├── analysis/
    ├── feedback/
    └── superpowers/
        ├── plans/
        ├── specs/
        └── execution/
```

顶层继续保留：

```text
README.md
ARCHITECTURE.md
AGENTS.md
CLAUDE.md
```

## 文档分层

### 事实源

这些文档需要和代码、CLI、产品边界保持同步：

- `README.md`：项目入口、能力摘要和快速开始。
- `docs/README.md`：唯一文档导航入口。
- `docs/REQUIREMENTS.md`：产品边界、质量目标和不做什么。
- `ARCHITECTURE.md`：当前架构、数据流和模块边界。
- `docs/USER_MANUAL.md`：安装、命令和故障排查。
- `AGENTS.md`：Codex 与通用 Agent 项目操作规则。
- `CLAUDE.md`：Claude Code 项目操作规则。
- `.agents/skills/`：项目 Skill 事实源。
- `src/novel_material/storage/migrations/README.md`：数据库迁移子系统契约。

### 当前工作文档

这些文档保留在 `docs/` 可见位置，但不具备事实源裁决权：

- `docs/search-benchmark.md`：检索容量与质量门禁状态。
- `docs/feedback.md`：当前未解决反馈和待办。
- `docs/current/plans/`：仅存放仍在执行或即将执行的计划。

### 历史归档

这些文档归档后默认不维护，只作为追溯证据：

- `docs/code-review-report.md` -> `docs/archive/reviews/code-review-report.md`
- `docs/code-review-llm-response-contract-report.md` -> `docs/archive/reviews/code-review-llm-response-contract-report.md`
- `docs/analysis/` -> `docs/archive/analysis/`
- `docs/feedback/archive/` -> `docs/archive/feedback/`
- `docs/superpowers/plans/` -> `docs/archive/superpowers/plans/`
- `docs/superpowers/specs/` -> `docs/archive/superpowers/specs/`
- `docs/superpowers/execution/` -> `docs/archive/superpowers/execution/`

本设计文档和后续实施计划在 Superpowers 流程中会先生成到 `docs/superpowers/`，执行归档时应避免把正在执行的本轮设计和计划误归档；完成后可按最终状态移动或在索引中标记为当前整理记录。

## 导航规则

`docs/README.md` 更新为四类入口：

1. 事实源：README、需求、架构、用户手册、Agent 指南。
2. 当前工作：feedback、search benchmark、current plans。
3. 历史归档：archive 下的 reviews、analysis、feedback、superpowers。
4. 非项目文档：material、data、pytest cache、egg-info、构建产物。

文档冲突时，以如下顺序裁决：

1. 用户当前请求。
2. `AGENTS.md` / `CLAUDE.md` 中的项目操作规则。
3. `docs/REQUIREMENTS.md`。
4. `ARCHITECTURE.md`。
5. `docs/USER_MANUAL.md`。
6. `README.md`。
7. 历史归档仅供参考，不参与裁决。

## 链接维护

归档执行时需要同步检查 Markdown 链接：

- 更新 `docs/README.md` 中所有工作记录入口。
- 更新仍在事实源文档中引用审查报告、复盘或历史计划的链接。
- 历史归档内部链接尽量修复；无法低风险修复时，在 `docs/archive/README.md` 说明历史链接可能指向归档前路径。
- 不为 `material/` 和 `data/` 生成文档导航。

## Skill 镜像规则

- `.agents/skills/` 是项目 Skill 事实来源。
- `.claude/skills/` 是由 `scripts/sync_agent_skills.py` 生成的镜像，不手工归档或移动。
- 当前已发现镜像漂移：`.claude` 缺少 `git-commit-push/SKILL.md`，多出 `commit-msg/SKILL.md`。实施阶段应通过同步脚本或单独任务修复，而不是在文档归档中手工改镜像。

## 验收标准

- `docs/README.md` 能清楚回答“哪些文档需要维护、哪些只是归档”。
- 顶层和 `docs/` 根部只保留事实源与当前工作文档。
- 历史审查、复盘、已解决反馈和 Superpowers 历史记录位于 `docs/archive/`。
- `material/`、`data/`、`.pytest_cache/`、构建元数据未被纳入项目文档体系。
- 所有仍存在于事实源和当前工作文档中的相对链接可解析。
- `git status` 能清楚展示本轮移动与索引更新，不混入用户已有未提交改动。

## 风险与缓解

- 风险：移动历史文件导致旧链接失效。
  缓解：优先修复事实源和当前工作文档链接；历史内部链接按低风险原则修复，并在归档说明中标注。
- 风险：把正在执行的 Superpowers 设计或计划提前归档。
  缓解：实施时先识别本轮文档，保留在当前流程位置，完成后再决定是否归档。
- 风险：误把素材文本当作文档处理。
  缓解：归档扫描明确排除 `material/`、`data/`、`.pytest_cache/` 和构建元数据目录。
- 风险：`AGENTS.md`、`CLAUDE.md` 与真实 CLI 继续漂移。
  缓解：实施计划中单独安排 CLI 速览校准任务，并用 `python -m novel_material.cli.main <group> --help` 核对。
