# Packet 4：世界观 LLM 输出归一化与契约校验

**目标：** 新增 layered 世界观响应归一化，生成稳定实体 ID 并校验关系引用，同时保留旧 `normalize_worldbuilding_response` 契约。

**详细步骤来源：** 完整计划 Task 4。

**关键文件：**

- `src/novel_material/worldbuilding/normalizer.py`
- `src/novel_material/pipeline/worldbuilding.py`
- `tests/worldbuilding/test_normalizer.py`
- `tests/pipeline/test_llm_response_contracts.py`

**完成验证：**

```bash
python -m pytest tests/worldbuilding/test_normalizer.py tests/pipeline/test_llm_response_contracts.py -v
python -m compileall -q src/novel_material/worldbuilding src/novel_material/pipeline
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-05-layered-writer-pipeline.md`。

**提交：** `feat(worldbuilding): 增加分层世界观响应归一化`
