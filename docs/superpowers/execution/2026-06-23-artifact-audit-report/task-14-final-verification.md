# Packet 14：全量验证与真实只读验收

**目标：** 执行第一期完整测试、CLI/compile 检查和真实兜底素材只读验收。

**详细步骤来源：** 完整计划 `Task 9` 的 Step 3–7 与“第一期完成门禁”。

```bash
sed -n '/- \[ \] \*\*Step 3: 运行第一期完整测试/,/^## 第一期完成门禁/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
sed -n '/^## 第一期完成门禁/,$p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**禁止：** 不调用真实 LLM，不同步数据库，不修改真实素材事实文件。

**完成验证：** 全量开列 pytest 为 0 failed；两个 CLI help、compileall、差异检查通过；`nm_novel_20260621_4si2` 稳定报告 `character_profile_fallback` 且原文件哈希不变。

**提交：** 仅在出现验收修正或文档记录时提交；否则更新 STATE 为 complete，并记录最后通过命令与提交。

**完成后：** 开始编写第二期独立实施计划，不直接修改第二期业务代码。
