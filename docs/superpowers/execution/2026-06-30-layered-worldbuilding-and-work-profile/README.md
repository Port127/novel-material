# 分层世界观与作品画像执行包

本目录用于第三期跨会话执行。除非当前 packet 明确要求，不读取完整计划、不读取完整历史对话。

## 执行顺序

| Packet | 文件 | 目标 |
|---|---|---|
| 1 | `task-01-state-and-index.md` | 建立执行状态与索引 |
| 2 | `task-02-worldbuilding-models-reader.md` | 世界观契约模型与旧格式兼容读取 |
| 3 | `task-03-dimension-router.md` | 题材维度路由 |
| 4 | `task-04-normalizer-contract.md` | 世界观 LLM 输出归一化与契约校验 |
| 5 | `task-05-layered-writer-pipeline.md` | 写入 layered 世界观结构并接入 pipeline |
| 6 | `task-06-audit-report-worldbuilding.md` | 世界观审计与报告质量信号 |
| 7 | `task-07-work-profile-contract.md` | `work_profile.yaml` 契约 |
| 8 | `task-08-profile-stage-cli.md` | `profile` 阶段与 CLI/orchestrator/status/continue 接入 |
| 9 | `task-09-storage-embedding-sync.md` | embedding 与 storage 兼容新世界观 |
| 10 | `task-10-search-world-metadata.md` | `search world` 适配新实体 metadata |
| 11 | `task-11-docs-final-verification.md` | 权威文档、全量验证和真实只读 smoke |

## 恢复步骤

1. 读取 `AGENTS.md`。
2. 读取本目录 `STATE.md`。
3. 读取 `STATE.md` 指向的当前 packet。
4. 执行 `git status --short`。
5. 执行 `git log -3 --oneline`。
6. 继续当前 packet，完成后更新 `STATE.md` 并提交。

## 固定边界

- 不纳入用户原有 `docs/feedback.md` 修改。
- 默认测试不调用真实 LLM、不连接真实数据库、不修改真实素材。
- 真实素材 LLM 重跑或修复必须单独授权。
- 旧世界观四文件只读兼容，不在读取时自动改写。
- 不改变 embedding 维度。
- 未完成人工 Golden Query 前，不声称检索质量提升。
