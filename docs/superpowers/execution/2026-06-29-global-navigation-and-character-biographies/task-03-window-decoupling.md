# Packet 03：`--window` 与前置导航解耦

**目标：** `--window` 只控制章级窗口；前置导航由运行模式和显式开关控制。

**详细步骤来源：** 完整计划 `Task 3`。

```bash
sed -n '/^## Task 3：解除 `--window` 与前置导航绑定/,/^## Task 4：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**完成验证：**

```bash
python -m pytest tests/cli/test_pipeline_common.py tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/pipeline/test_navigation_window_decoupling.py -v
python -m novel_material.cli.main pipeline full --help
python -m novel_material.cli.main pipeline analyze --help
```

**提交：** `feat(pipeline): 解耦前置导航与滑动窗口`
