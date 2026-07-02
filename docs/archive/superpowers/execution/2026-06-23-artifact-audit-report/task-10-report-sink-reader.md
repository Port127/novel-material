# Packet 10：ReportSink 与 JSONL reader

**目标：** 在 RunCompleted 时落盘报告，并支持按 run_id 重读轮转 JSONL。

**详细步骤来源：** 完整计划 `Task 7` 的 Step 2、6–9。

```bash
sed -n '/^### Task 7：/,/^### Task 8：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `reporting/sink.py`、`run_logging/reader.py` 及对应测试。

**完成验证：** `python -m pytest tests/reporting/test_sink.py tests/run_logging tests/runtime/test_dependencies.py -v`。

**提交：** `feat(report): 接入报告 sink 与运行事件重读`。

**完成后：** 更新 STATE 指向 `task-11-pipeline-gating.md`。
