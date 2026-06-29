# Packet 1：执行状态目录与 packet 索引

**目标：** 建立第三期跨会话执行入口。本 packet 通常随 plan 一起完成；若恢复时已提交，可直接更新 STATE 指向 Packet 2。

**详细步骤来源：** `docs/superpowers/plans/2026-06-30-layered-worldbuilding-and-work-profile.md` 的 Task 1。

**完成验证：**

```bash
find docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile -maxdepth 1 -type f | sort
git diff --check -- docs/superpowers/plans/2026-06-30-layered-worldbuilding-and-work-profile.md docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile
git status --short
```

**完成后：** 更新 `STATE.md`，并将 `last_good_commit` 设为本 packet 提交后的短 hash：

```yaml
status: ready
current_packet: task-02-worldbuilding-models-reader.md
last_completed_packet: task-01-state-and-index.md
```

**提交：** `docs(plan): 拆分分层世界观第三期计划`
