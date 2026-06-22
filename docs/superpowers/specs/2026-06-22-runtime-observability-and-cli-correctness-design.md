# 运行结果、日志与终端解耦设计

**状态：** 已完成对话确认，待实施

**日期：** 2026-06-22

**目标版本：** Novel Material V3 运行可靠性增强

## 1. 决策摘要

本次改进不是单纯美化日志或进度条，而是修复“业务结果、流水线状态、日志描述、终端显示和退出码互相矛盾”的系统性问题。

采用一个事实来源、两个独立消费者的结构：

```text
Pipeline / Search / Storage / Material
                │
                ├── 返回 RunResult
                └── 发布 RunEvent
                          │
                   Runtime Dispatcher
                    ├──────────────┐
                    ▼              ▼
              run_logging/      terminal/
              结构化持久化        人机交互
```

核心决策：

1. `runtime` 只定义中立运行契约、请求上下文、同步分发和结果聚合。
2. `run_logging` 和 `terminal` 是两个独立模块，禁止互相 import。
3. 业务层不得直接依赖 Rich、`print()` 或 logging handler。
4. 当前运行是否成功只由 `RunResult` 决定，不能根据文件数量、日志文字或数据库探测二次猜测。
5. 流水线持久化状态由 Pipeline 自己维护；日志和终端都不是断点事实来源。
6. 新日志使用 JSONL；旧日志不迁移、不清洗、不删除。
7. 默认不修复、清洗、补写或重跑已有素材数据。只有用户显式执行会改变数据的命令时，才按该命令的既有业务范围处理。
8. `storage sync` 的自动修复副作用改为显式选择，普通同步只校验和同步，不静默重分析 YAML。
9. 不引入 OpenTelemetry SDK、Collector、远程日志平台、消息队列或新的数据库。

## 2. 已确认问题

### 2.1 流水线真实性

- `chapter_insights` API 或 schema 失败后仍写入占位/无效文件。
- insights 最终无条件返回成功，完成判定只计算 YAML 文件数量。
- 断点续传会跳过已经存在但无效的文件。
- `full`、`continue` 和单阶段命令丢弃服务返回值，再通过文件或数据库反推成功。
- 数据库连接失败与“尚未同步”被合并为同一个状态。
- 处理进度 100% 被错误呈现为数据有效率 100%。

这些问题导致同一素材可以同时出现 `finalized`、深度分析完成、数据库同步完成、insights 校验失败和数据库未完成等相互冲突的结论。

### 2.2 日志系统

- 测试和短命进程污染正式 `logs/`，产生大量碎片文件。
- 异常日志读取全局“最后一次成功调用”，导致 `request_id`、attempt 耗时串线。
- 时间戳只有时分秒，跨日后无法独立解释。
- 文本日志缺少稳定 schema、运行 ID、阶段 ID和生命周期。
- WARNING 洪水掩盖真正故障。
- `thinking=disabled` 与 `thinking_tokens`/阈值警告语义冲突。
- 原始模型片段、服务商异常和密钥指纹存在信息暴露风险。
- 没有轮转、保留期限、写入失败和丢失事件策略。
- pipeline、search、embedding 各写独立文件，无法重建一次命令的完整调用链。

### 2.3 终端与 CLI

- 多个失败路径退出码仍为 0，甚至继续打印绿色完成。
- ERROR/WARNING 在 `silent_console` 期间完全不可见。
- Rich `TimeRemainingColumn` 把批次完成后的瞬时进度误判为整体速度，稳定显示秒级假 ETA。
- 手工 spinner、Rich Progress、原生 `print` 和 logging 同时写终端。
- stdout/stderr 没有契约，错误污染机器输出和 JSON。
- 非 TTY、窄终端、无颜色和安静模式没有统一降级策略。
- 动态素材文本可能被 Rich 当作 markup 解释。
- 参数错误暴露 Python/Pydantic traceback。
- 不确定总量任务完成后仍保留旋转图标。
- `event --keyword` 无效，`--semantic` 命名与实际行为不一致。
- 两处提示原样输出 `{material_id}`。
- `nm` 在 macOS 与 `/usr/bin/nm` 冲突。
- 终端帮助中英文混杂；优先级低于语义正确性。

完整证据见 `docs/code-review-report.md`。

## 3. 数据边界

### 3.1 本次不做

- 不修改当前 `data/novels/` 中的 YAML、NPZ 或索引文件。
- 不重跑当前 90 个无效 insight。
- 不回填旧运行日志的 `run_id` 或结构化字段。
- 不清理现有 `logs/*.log`。
- 不为让测试通过而改造测试素材。
- 不自动连接真实 PostgreSQL 执行同步、迁移或修复。

### 3.2 允许的新行为

- 新运行从启用版本开始生成结构化日志和运行状态 sidecar。
- 用户未来显式执行 `continue` 时，系统可以把缺失或无效结果识别为待处理项；本计划本身不会触发该命令。
- 必须改变持久化契约时，只新增向后兼容的 sidecar；不要求回填历史素材。
- 数据修复必须由显式参数或独立命令授权，并记录审计事件。

### 3.3 兼容策略

旧素材仍可只读查询。没有新运行状态 sidecar 时：

- `status` 可以执行只读校验并标记 `legacy_unverified`。
- 文件存在只能说明 `present`，不能显示为 `success`。
- 数据库无法连接显示 `unknown`，不能显示 `not_synced`。
- 不在查询过程中写回任何状态。

## 4. 模块设计

### 4.1 `runtime/`

```text
src/novel_material/runtime/
├── contracts.py     # RunEvent、Diagnostic、StageResult、RunResult
├── context.py       # contextvars：run/stage/request 上下文
├── dispatcher.py    # 同步事件分发与 sink 故障隔离
├── diagnostics.py   # 无文件副作用的旧 logger 迁移适配
├── heartbeat.py     # 长任务低频存活事件与可停止 worker
├── summary.py       # 计数、Token、诊断聚合
└── testing.py       # FakeClock、MemoryEventSink
```

`runtime` 不依赖 Typer、Rich、Python logging、pipeline 或 storage。

状态集合：

```text
pending → running → success
                  ↘ degraded
                  ↘ failed
                  ↘ interrupted
```

`RunResult` 至少包含：

- `run_id`、command、operation、material_id；
- started/finished/duration；
- overall status 和 exit code；
- 每阶段 `StageResult`；
- expected、processed、succeeded、degraded、failed、remaining；
- API 次数和 input/output/reasoning/total tokens；
- 聚合后的 diagnostics 和 next actions。

### 4.2 Pipeline 状态

Pipeline 新增自己的运行状态 sidecar 和显式索引：

```text
data/novels/{material_id}/runs/
├── {run_id}.json
├── latest.json
└── active.lock
```

`{run_id}.json` 只为新运行创建，记录 `created_at`、`updated_at`、单调递增的 `generation`，以及阶段开始、完成、降级、失败和中断。每次先原子替换运行文件，再原子替换 `latest.json`；`status` 和 `continue` 禁止通过文件名、mtime 或目录遍历猜测最新运行。

同一素材同一时刻只允许一个写运行。启动时通过独占创建 `active.lock` 获取 lease；并发运行返回稳定 diagnostic 和非零退出码。`status` 只读报告活跃或遗留 lease，不自动清理；用户显式执行 `continue` 时，只有确认原 PID 已不存在后才能接管 stale lease，并把上一运行记录为 interrupted。sidecar 或索引损坏时返回 `state_corrupt`，不得静默退回文件数量推断。

所有状态和索引更新都采用同目录临时文件、flush、`fsync` 和 `os.replace`。这些文件属于 Pipeline 状态，不属于日志。

当前运行使用内存中的 `RunResult`；`status` 和 `continue` 才读取持久化状态。没有 sidecar 的历史素材使用只读兼容检查，并明确标记未验证。

insights 规则调整为：

- LLM 未返回某章时不写 insight 数据文件；
- repair 后仍不满足 schema 时不覆盖/创建事实文件；
- schema 合法但质量较低时可以保存为 `degraded`，并降低 confidence；
- 阶段结果区分成功、降级、失败和待重试数量；
- `continue` 只把缺失或校验失败的章节列为 pending，不因文件名存在而跳过。

### 4.3 `run_logging/`

```text
src/novel_material/run_logging/
├── sink.py          # JsonlSink 与写入失败报告
├── serializer.py    # schema_version=1 JSONL
├── redaction.py     # 白名单、脱敏、控制字符清理
├── aggregation.py   # 重复诊断限流与汇总
├── retention.py     # 只管理新格式日志
└── testing.py       # MemorySink、NullSink
```

新日志目录：

```text
logs/YYYY-MM-DD/{command}_{run_id}.jsonl
```

每条事件字段：

- `schema_version`、`event_name`、`event_id`；
- `occurred_at`、`observed_at`；
- `severity_text`、`severity_number`；
- `run_id`、`stage_id`、内部 `request_id`、可空的 `provider_request_id`；
- command、component、operation、material_id；
- status、duration_ms、attributes。

事件集合保持小而稳定：

- `RunStarted`
- `StageStarted`
- `ProgressUpdated`
- `DiagnosticRaised`
- `OperationStarted`
- `OperationCompleted`
- `StageCompleted`
- `RunCompleted`
- `HeartbeatRecorded`
- `AuditRecorded`

每次 LLM attempt 在发送请求前生成新的内部 `request_id`；失败请求也必须拥有该 ID。服务商响应 ID 只在收到响应后写入 `provider_request_id`，不能借用上一次成功响应的值。

LLM attributes 记录 provider、model、operation、attempt、重试上限、退避、timeout、Token、finish reason、预期/返回/缺失数量、校验和降级原因。默认不记录 prompt、原文、完整模型输出或未清洗异常。脱敏同时使用字段白名单、敏感键规则和值模式规则，覆盖 bearer token、常见 API key、数据库连接串和异常文本中的凭据片段。

Search attributes 记录 mode、候选上限、时间预算、通道候选数、通道耗时、embedding 配置摘要、rerank 和降级原因。查询正文默认不进日志，只记录长度与指纹。

Audit 事件覆盖 import、delete、sync、migration 和 tags 变更，记录目标、确认方式、修改数量摘要、是否允许修复和结果，不记录完整数据。

### 4.4 `terminal/`

```text
src/novel_material/terminal/
├── reporter.py      # stdout/stderr 与最终摘要
├── progress.py      # 唯一 Progress 工厂
├── eta.py           # 批次级稳健 ETA
├── modes.py         # TTY、plain、quiet、JSON
├── errors.py        # 参数/业务异常到用户消息和退出码
└── testing.py       # RecordingTerminal
```

输出模式：

- TTY：Rich 进度、表格和颜色。
- 非 TTY：稳定纯文本，不含 spinner、动态刷新和 ANSI。
- JSON：stdout 只能包含单个可解析 JSON 文档；diagnostic 进入 stderr。
- quiet：只输出最终结果或错误。

进度显示：

```text
阶段 2/7 | 章级分析 | 420/1780 | 24%
已用 2:07:18 | 剩余 ~5:53:00
成功 410 | 降级 8 | 失败 2 | 待处理 1360
```

ETA 规则：

- 删除 Rich 的 `TimeRemainingColumn`。
- 使用真实批次完成耗时，不使用批内逐章瞬时更新速度。
- 至少两个有效批次后才显示估算；之前显示“估算中”。
- 使用最近批次中位数，重试等待计入已用时间。
- 断点续传以本次运行 pending 数量为分母，不把历史处理时间伪装为本次耗时。

退出码：

- `0`：完整成功；
- `1`：运行、校验或阻断性业务失败；
- `2`：参数和使用方式错误；
- `3`：降级完成；
- `130`：用户中断。

stdout/stderr：

- stdout：正常结果、稳定 JSON、成功摘要；
- stderr：错误、警告、诊断和进度；
- 用户数据使用 `Text(value)`，不解释 Rich markup。

## 5. 错误与降级

- 业务阶段失败：生成 failed `StageResult`，编排器决定是否继续。
- 允许局部失败：继续处理，但总结果至少为 degraded。
- required sink（默认启用的 JSONL 持久化）失败：不阻断业务执行，但运行结果标记 degraded，备用 stderr 只提示一次。
- best-effort sink 失败：记录内存诊断并隔离故障，不改变业务结果；终端渲染不作为 required sink。
- Rich 渲染失败：切换到 plain reporter，不影响日志。
- 一个消费者异常：不能阻止另一个消费者收到事件。
- 数据库探测失败：状态为 unknown，并保留错误码；不能伪装成未同步。
- `KeyboardInterrupt`：完成当前状态持久化，发布 interrupted 事件并退出 130。
- 未预期异常：用户终端显示简短错误码；完整且已脱敏的异常结构进入 JSONL。

## 6. CLI 行为调整

- Pipeline 单阶段、`full`、`continue` 统一消费 `RunResult`。
- Validate 单素材和 `--all` 有失败项时退出 1。
- Storage 全量同步返回 total/succeeded/failed/skipped，不再只返回成功数量。
- `storage sync` 默认不自动修复；增加显式 `--repair`，使用前提示会修改 YAML 和产生 API 成本。
- Material 删除缺少 ID 属于使用错误；删除失败退出 1，用户取消仍退出 0。
- Search 只保留 `--mode quality|exact`；`--semantic` 保留一个版本作为弃用别名并映射为 `exact`。`mode` 的解析必须保留“未显式传入”状态，任何显式 `--mode` 与 `--semantic` 同时出现都退出 2。
- 删除无效 `event --keyword`。
- Typer/Pydantic 参数错误转换成简洁消息，不输出 traceback。
- 修复包含 `{material_id}` 的提示，通过 next-action renderer 生成命令。
- 新增 `novel-material` 脚本入口并保留 `nm`，文档要求先验证 PATH。
- 帮助界面本地化作为最后的低优先级任务，不阻塞正确性验收。

## 7. 测试设计

### 7.1 单元测试

- Runtime：不可变模型、状态聚合、exit code、context 隔离、sink 故障隔离。
- Logging：JSONL schema、RFC 3339、脱敏、控制字符、轮转、保留、警告聚合和测试隔离。
- Terminal：TTY/plain/JSON/quiet、stdout/stderr、Rich Text、终态 spinner、ETA 假时钟。
- Pipeline：insight 缺失/invalid 不写事实文件、legacy_unverified、DB unknown、原子状态写入。

### 7.2 CLI 契约测试

- 所有失败路径检查非零退出码。
- JSON 模式 stdout 可解析且无进度文本。
- 非 TTY 无 ANSI 和动态刷新。
- WARNING/ERROR 在进度期间可见。
- `full`、`continue` 和单阶段使用一致摘要。
- 搜索参数、无效选项、删除确认、同步汇总和 macOS 入口有回归测试。

### 7.3 集成测试

同一组事件同时送入 MemoryLogSink 和 RecordingTerminal，验证：

- 两边看到相同 run/stage/status；
- 两个消费者互不引用；
- 任一消费者失败不影响另一个；
- RunResult 与最后的 RunCompleted 一致；
- 测试期间正式 `logs/` 文件数量不增加。

### 7.4 数据安全测试

- 测试只使用 `tmp_path`、fake DB 和 fake LLM。
- 禁止测试运行 `nm pipeline full`、真实 storage sync 或已有素材 repair。
- 阶段一开始就记录 `data/novels` 全量文件和旧日志的 SHA-256 基线；每个实施 Task 完成后都执行校验。
- 基线必须覆盖未跟踪文件和嵌套旧日志，不能只依赖 `git diff`；基线缺失时不得宣称零变化。
- 最终验收再次校验同一份基线，确认整个实施周期零变化。

## 8. 实施阶段

1. 固化回归测试和测试隔离。
2. 建立 Runtime 契约、context 和 dispatcher。
3. 修复 Pipeline 结果真实性和新运行状态 sidecar。
4. 实现独立结构化日志模块。
5. 先把全局 LLM 统计替换为请求局部 telemetry，并保留无全局状态的短期兼容层。
6. 接入 Pipeline、Search、Audit 领域事件和具有明确 start/stop/join 生命周期的 heartbeat worker。
7. 实现独立终端模块和正确 ETA。
8. 先接入短命令和搜索，验证 stdout/stderr/JSON。
9. 先统一 Pipeline 阶段 adapter，再接入单阶段、`full` 和 `continue` 编排。
10. 接入 validate、storage、material 和 tags audit。
11. 迁移所有兼容 accessor 调用后，再删除旧 progress/logging 耦合与兼容层。
12. 更新文档并执行全量零数据变更验收。

每个阶段都必须先写失败测试、确认失败、实现最小闭环、运行定向与全量测试，再提交。日志和终端可以在 Runtime 完成后分别实现和测试，但只有 Pipeline 结果契约可靠后才能宣称整体完成。

## 9. 验收标准

- 同一运行只存在一个 `RunResult` 成功结论。
- 任何阻断失败都不再退出 0 或显示绿色完成。
- `processed=total` 不等价于 `succeeded=total`。
- 无效 insight 不再被计入成功，也不会因文件存在被跳过。
- DB 不可达显示 unknown。
- 用户现场的 `420/1780` 批次更新不再出现 `0:00:02` 假 ETA。
- JSON 模式 stdout 始终可解析。
- 进度期间 WARNING/ERROR 可见。
- 新日志可以按 run/stage/request 关联，且默认不包含敏感正文。
- 测试不创建正式日志。
- 不修改、清洗、迁移或重跑任何已有素材和旧日志。
- `docs/code-review-report.md` 的 28 项问题都有对应测试、修复任务或明确延期说明。

## 10. 采用的外部原则

- [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)：借鉴事件名、发生/观测时间、severity、resource 和 trace/span 关联字段；不引入 SDK。
- [OpenTelemetry GenAI Events](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-events/)：借鉴 provider/model/operation/token/error 语义；实验字段不作为外部稳定 API。
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)：采用审计轨迹、敏感字段排除和日志注入防护。
- [Python Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html)：使用 `contextvars` 隔离请求上下文；只有证据证明同步 I/O 阻塞时才考虑 QueueHandler/QueueListener。
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)：关联 ID 使用不含业务数据的随机不透明值。
