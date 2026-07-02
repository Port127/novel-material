# Packet 06：dispatcher 上下文与 LLM telemetry

**目标：** 让嵌套 LLM 调用继承运行 dispatcher，并汇总尝试、完成、Token 与成本。

**详细步骤来源：** 完整计划 `Task 5` 的 Step 1、3、4、6。

```bash
sed -n '/^### Task 5：/,/^### Task 6：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `runtime/{context,summary}.py`、`infra/llm.py` 及 runtime/telemetry 测试。

**完成验证：** `python -m pytest tests/runtime tests/infra/test_llm_telemetry.py -v`。

**提交：** `feat(runtime): 贯通运行 dispatcher 与 LLM 指标`。

**完成后：** 更新 STATE 指向 `task-07-orchestrator-events.md`。
