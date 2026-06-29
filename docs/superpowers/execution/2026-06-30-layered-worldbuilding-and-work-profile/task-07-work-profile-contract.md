# Packet 7：`work_profile.yaml` 契约

**目标：** 新增作品画像 Pydantic 契约和提示词构造器，要求证据索引引用下层事实产物。

**详细步骤来源：** 完整计划 Task 7。

**关键文件：**

- `src/novel_material/pipeline/work_profile_models.py`
- `src/novel_material/pipeline/work_profile_prompt.py`
- `tests/pipeline/test_work_profile_contract.py`

**完成验证：**

```bash
python -m pytest tests/pipeline/test_work_profile_contract.py -v
python -m compileall -q src/novel_material/pipeline
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-08-profile-stage-cli.md`。

**提交：** `feat(profile): 增加作品画像契约`
