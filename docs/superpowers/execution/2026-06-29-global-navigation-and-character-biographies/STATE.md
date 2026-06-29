# 执行状态

```yaml
feature: global-navigation-and-character-biographies
phase: 2
status: ready
current_packet: task-11-docs-final-verification.md
last_completed_packet: task-10-performance-smoke.md
last_good_commit: 871583d
worktree: current_main_user_approved
blocking_issue: null
```

## 最近验证

- `python -m pytest tests/pipeline/test_character_performance_budget.py -v`：1 passed；新增预算测试首跑通过，说明前序实现已满足只对目标人物生成完整小传。
- `python -m pytest tests/pipeline/test_character_performance_budget.py tests/reporting/test_performance_baseline.py -v`：2 passed。
- `python -m pytest tests/audit tests/reporting tests/runtime tests/run_logging tests/pipeline tests/terminal tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/validation -v`：260 passed。
- `python -m novel_material.cli.main validate artifacts nm_novel_20260621_4si2`：退出码 3，符合真实素材只读 smoke 预期；未执行 LLM 修复。
- 真实素材 `nm_novel_20260621_4si2` 非 `reports/` 文件：前后均为 2325 个，digest 均为 `8ff8b12156e6009db2bb49df2f84460b55ad2c1718085f2f805cfcaf97b8005b`。
- `python -m compileall -q src/novel_material`：通过。
- `git diff --check -- . ':(exclude)docs/feedback.md'`：通过。
- Packet 10 提交：`871583d`。
- 当前工作区已知用户修改：`docs/feedback.md`，不得纳入第二期提交。

## 已确认且不得遗失

- 第二期只做前置导航、`--window` 解耦、主要人物选择、完整小传和定向修复。
- 第三期的分层世界观、实体关系、`work_profile.yaml`、存储和搜索适配不在本期。
- 旧 `evaluation.yaml` 只读兼容，不在读取时自动改写。
- 真实素材默认只读验收；真实 LLM 修复必须单独问用户。
- 未完成人工检索基线前，不声称检索质量提升。

## 本次开始动作

1. 打开 `task-11-docs-final-verification.md`。
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
