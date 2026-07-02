# Packet 01：evaluation 3.0.0 模型与旧版适配器

**目标：** 建立前置导航模型，支持新 `schema_version: 3.0.0`，并只读适配旧 `2.0.1`。

**详细步骤来源：** 完整计划 `Task 1`。

```bash
sed -n '/^## Task 1：建立 evaluation 3.0.0 模型与旧版适配器/,/^## Task 2：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**禁止：** 不修改真实素材；不调用 LLM；不改写旧 evaluation 文件。

**完成验证：**

```bash
python -m pytest tests/pipeline/test_evaluation_models.py tests/validation/test_schema.py -v
```

**提交：** `feat(evaluation): 增加前置导航模型兼容读取`
