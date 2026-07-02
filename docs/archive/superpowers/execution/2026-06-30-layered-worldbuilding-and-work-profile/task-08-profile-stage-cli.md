# Packet 8：`profile` 阶段与 CLI/orchestrator/status/continue 接入

**目标：** 新增 `nm pipeline profile nm_xxx`，并让 full/continue/status 识别 `profile` 阶段。

**详细步骤来源：** 完整计划 Task 8。

**关键文件：**

- `src/novel_material/pipeline/work_profile.py`
- `src/novel_material/pipeline/stages.py`
- `src/novel_material/cli/pipeline.py`
- `src/novel_material/cli/pipeline_common.py`
- `src/novel_material/pipeline/orchestrator.py`
- `src/novel_material/pipeline/progress.py`
- `tests/pipeline/test_work_profile_stage.py`
- `tests/pipeline/test_orchestrator.py`
- `tests/cli/test_pipeline_contract.py`
- `tests/cli/test_command_contracts.py`

**完成验证：**

```bash
python -m pytest tests/pipeline/test_work_profile_stage.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py -v
python -m novel_material.cli.main pipeline profile --help
python -m compileall -q src/novel_material/pipeline src/novel_material/cli
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-09-storage-embedding-sync.md`。

**提交：** `feat(profile): 接入作品画像流水线阶段`
