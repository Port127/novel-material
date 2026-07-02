# Packet 09：continue/status 阶段契约

**目标：** 让 status/continue 识别 v3/v2 evaluation，并按 navigation 开关恢复阶段。

**详细步骤来源：** 完整计划 `Task 9`。

```bash
sed -n '/^## Task 9：更新 continue\/status 与阶段契约/,/^## Task 10：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**完成验证：**

```bash
python -m pytest tests/pipeline/test_state.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/cli/test_pipeline_common.py -v
```

**提交：** `feat(pipeline): 更新导航阶段断点语义`
