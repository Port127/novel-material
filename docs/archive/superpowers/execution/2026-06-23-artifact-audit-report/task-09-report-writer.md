# Packet 09：Markdown 与原子 writer

**目标：** 生成 Markdown，并幂等写入 immutable run YAML 与原子 latest 文件。

**详细步骤来源：** 完整计划 `Task 7` 的 Step 1、3–5。

```bash
sed -n '/^### Task 7：/,/^### Task 8：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `reporting/{markdown,writer}.py`、`infra/path_service.py` 及 writer/markdown 测试。

**完成验证：** `python -m pytest tests/reporting/test_markdown.py tests/reporting/test_writer.py -v`。

**提交：** `feat(report): 原子写入机器报告与 Markdown`。

**完成后：** 更新 STATE 指向 `task-10-report-sink-reader.md`。
