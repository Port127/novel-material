# Packet 02：evaluate 写入前置导航

**目标：** 让 evaluate 生成 `evaluation.yaml` 3.0.0，并记录 sample coverage。

**详细步骤来源：** 完整计划 `Task 2`。

```bash
sed -n '/^## Task 2：让 evaluate 写入 3.0.0 前置导航/,/^## Task 3：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**禁止：** 不调用真实 LLM；测试使用 normalize/fixture/fake。

**完成验证：**

```bash
python -m pytest tests/pipeline/test_evaluation_models.py tests/pipeline/test_evaluation_v3.py tests/pipeline/test_llm_response_contracts.py -v
```

**提交：** `feat(evaluation): 输出前置导航三点零`
