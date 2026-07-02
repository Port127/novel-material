# Packet 5：写入 layered 世界观结构并接入 pipeline

**目标：** 让 `nm pipeline worldbuilding` 写入 `_index.yaml`、`overview.yaml`、`dimensions.yaml`、`entities/*.yaml` 和 `relations.yaml`。

**详细步骤来源：** 完整计划 Task 5。

**关键文件：**

- `src/novel_material/worldbuilding/writer.py`
- `src/novel_material/pipeline/worldbuilding.py`
- `tests/worldbuilding/test_writer.py`
- `tests/pipeline/test_worldbuilding_layered_pipeline.py`

**完成验证：**

```bash
python -m pytest tests/worldbuilding/test_writer.py tests/pipeline/test_worldbuilding_layered_pipeline.py tests/cli/test_pipeline_contract.py::test_remaining_single_stage_failures_exit_one -v
python -m compileall -q src/novel_material/worldbuilding src/novel_material/pipeline
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-06-audit-report-worldbuilding.md`。

**提交：** `feat(worldbuilding): 写入分层世界观产物`
