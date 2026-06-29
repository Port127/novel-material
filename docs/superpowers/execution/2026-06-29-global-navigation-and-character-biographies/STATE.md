# 执行状态

```yaml
feature: global-navigation-and-character-biographies
phase: 2
status: ready
current_packet: task-10-performance-smoke.md
last_completed_packet: task-09-state-continue-contract.md
last_good_commit: a35ab1e
worktree: current_main_user_approved
blocking_issue: null
```

## 最近验证

- `python -m pytest tests/pipeline/test_state.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py -v`：先出现 4 个预期失败，暴露 legacy inspection 缺少 `evaluation` 阶段与 `plan_continue` 缺少 `include_navigation` 参数。
- `python -m pytest tests/pipeline/test_state.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/cli/test_pipeline_common.py tests/pipeline/test_evaluation_models.py -v`：63 passed。
- `python -m compileall -q src/novel_material`：通过。
- `git diff --check -- . ':(exclude)docs/feedback.md'`：通过。
- Packet 09 提交：`a35ab1e`。
- 当前工作区已知用户修改：`docs/feedback.md`，不得纳入第二期提交。

## 已确认且不得遗失

- 第二期只做前置导航、`--window` 解耦、主要人物选择、完整小传和定向修复。
- 第三期的分层世界观、实体关系、`work_profile.yaml`、存储和搜索适配不在本期。
- 旧 `evaluation.yaml` 只读兼容，不在读取时自动改写。
- 真实素材默认只读验收；真实 LLM 修复必须单独问用户。
- 未完成人工检索基线前，不声称检索质量提升。

## 本次开始动作

1. 打开 `task-10-performance-smoke.md`。
2. 确认工作区除用户 `docs/feedback.md` 外没有未知修改。
3. 按 packet 内 TDD 步骤执行。

## 每次结束必须更新

- `status`：`ready`、`in_progress`、`blocked` 或 `complete`。
- `current_packet`、`last_completed_packet`、`last_good_commit`。
- 实际验证命令和结果。
- 若中断，记录未提交文件与下一条具体命令。

## 未来阶段

- 第三期：分层世界观、实体关系、作品画像、存储与检索适配。
- 规划依据：总体设计第 7、8、13–16 节。
