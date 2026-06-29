# Packet 05：完整小传契约与 prompt

**目标：** 定义主要人物完整小传字段、规范化 LLM 响应，并更新 core prompt。

**详细步骤来源：** 完整计划 `Task 5`。

```bash
sed -n '/^## Task 5：定义完整小传契约与响应规范化/,/^## Task 6：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**完成验证：**

```bash
python -m pytest tests/pipeline/test_character_biography.py tests/pipeline/test_llm_response_contracts.py -v
```

**提交：** `feat(characters): 定义主要人物完整小传契约`
