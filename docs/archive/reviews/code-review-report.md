# Code Review Report

**日期**：2026-06-22

**范围**：`src/novel_material/cli/`、`src/novel_material/infra/progress.py`、`src/novel_material/infra/logging_config.py`、`src/novel_material/pipeline/progress.py`、终端相关测试与文档

**语言**：Python 3.10+（Typer、Rich）
**问题总数**：28（🔴 14，🟡 10，🟢 4）

## 摘要

| 维度 | Critical | Suggestion | Nice to have | 合计 |
|---|---:|---:|---:|---:|
| 命名 | 0 | 1 | 0 | 1 |
| 格式 | 0 | 1 | 0 | 1 |
| 未使用引用 | 1 | 0 | 1 | 2 |
| 注释 | 0 | 0 | 1 | 1 |
| 逻辑 | 12 | 3 | 0 | 15 |
| 风格 | 0 | 1 | 1 | 2 |
| 职责边界 | 1 | 2 | 0 | 3 |
| 文档 | 0 | 2 | 1 | 3 |
| **合计** | **14** | **10** | **4** | **28** |

## 自动检查与复现

- `python -m compileall -q ...`：通过。
- `LOG_DIR=/tmp/novel-material-terminal-review-logs python -m pytest -q`：`186 passed, 1 skipped`。
- CLI 定向测试：`11 passed`。
- `ruff`：当前开发环境未安装，无法执行；`pyproject.toml` 也未配置 lint 规则。
- Rich ETA 最小复现：模拟每批等待 180 秒、随后 10 章在毫秒级连续更新；在 `420/1780` 时得到 `speed=1000/s`、`remaining=2s`、显示 `0:00:02`，与用户现场一致。
- 所有审查测试均将 `LOG_DIR` 指向 `/tmp`；未修改、清洗或重跑已有素材数据。

## 1. 命名

### 🟡 `--semantic` 的名称与实际行为不一致

- **文件**：`src/novel_material/cli/search.py:65-75`
- **代码**：

  ```python
  return {
      "mode": "exact" if semantic else mode,
  }
  ```

- **问题**：帮助文案称“启用语义检索”，实际行为是把 `mode` 强制改成 `exact`；默认 `quality` 本身也包含语义召回。用户无法从名称理解该选项是在启用语义能力、切换精确向量模式，还是覆盖 `--mode`。
- **建议**：只保留一个受约束的 `--mode quality|exact`；如需兼容 `--semantic`，标记为弃用别名并在冲突时给出明确提示。

## 2. 格式

### 🟡 Progress 布局重复定义且已经发生漂移

- **文件**：`src/novel_material/cli/pipeline.py:46-52,124-130,188-194,223-229,252-258,280-286,301-307,326-332,346-352,406-413,723-729`
- **代码**：

  ```python
  with Progress(
      SpinnerColumn(),
      TextColumn("[progress.description]{task.description}"),
      BarColumn(),
      TaskProgressColumn(),
      TimeRemainingColumn(),
      console=console,
  ):
  ```

- **问题**：同一布局复制十余次；`full` 带 `TimeRemainingColumn`，`continue` 不带，终端行为已不一致。
- **建议**：集中到一个终端进度工厂，根据确定/不确定任务选择布局；所有流水线入口共用同一组件。

## 3. 未使用引用

### 🔴 `event --keyword` 是无效选项

- **文件**：`src/novel_material/cli/search.py:189-208`
- **代码**：

  ```python
  keyword_mode: bool = typer.Option(False, "--keyword", help="使用关键词检索")
  # keyword_mode 后续没有参与 SearchRequest
  ```

- **问题**：带或不带 `--keyword` 构造出的 `SearchRequest` 完全相同；用户以为切换了检索策略，实际没有任何效果。
- **建议**：要么把选项传入明确的检索模式字段并增加请求断言测试，要么删除该选项。

### 🟢 StageTracker 保留多组未使用状态

- **文件**：`src/novel_material/infra/progress.py:134-138`
- **代码**：

  ```python
  self._prev_completed = 0
  self._prev_time = time.monotonic()
  self._eta_seconds = 0
  self._completed_stage_times = []
  ```

- **问题**：字段写入后未读取，容易让维护者误以为存在平滑 ETA 或阶段统计逻辑。
- **建议**：在终端进度重构时删除无效状态，或将其纳入统一计时模型并补测试。

## 4. 注释

### 🟢 时间列没有说明语义

- **文件**：`src/novel_material/cli/pipeline.py:411`
- **代码**：

  ```python
  TimeRemainingColumn()
  ```

- **问题**：终端只显示 `0:00:02`，没有“已用”或“剩余”标签；用户自然会将其理解为已用时。
- **建议**：统一显示 `已用 HH:MM:SS | 剩余 ~HH:MM:SS`，不要保留无标签的时间值。

## 5. 逻辑

### 🔴 单阶段命令失败后仍返回退出码 0

- **文件**：`src/novel_material/cli/pipeline.py:55-61,268-271,288-292,314-317,334-338`
- **代码**：

  ```python
  material_id = ingest_file(file_path)
  if material_id:
      console.print("入库成功")
  else:
      console.print("入库失败")
      # 没有 raise typer.Exit(1)
  ```

- **问题**：已复现 `ingest`、`outline`、`worldbuilding`、`characters`、`tags` 底层返回失败时，终端仍退出 0；其中多个命令还继续打印绿色“完成”。Shell、CI 和外部 Agent 会把失败当成功。
- **建议**：所有服务层返回值必须转换为统一命令结果；失败打印到 stderr 并退出非零。

### 🔴 `full` 和 `continue` 忽略阶段失败，数据库同步失败也退出 0

- **文件**：`src/novel_material/cli/pipeline.py:491-568,768-851`
- **代码**：

  ```python
  generate_outline(...)
  generate_worldbuilding(...)
  generate_characters(...)
  generate_tags(...)
  # 返回值未检查

  if not success:
      sync_failed = True
      console.print("数据库同步失败")
  # 命令最终没有非零退出
  ```

- **问题**：已复现最终表格同时出现“○ 未完成”“✗ 失败”，进程退出码仍为 0。编排器无法可靠判断完整流水线结果。
- **建议**：阶段结果聚合为 `success/degraded/failed`；存在阻断失败时退出 1，允许降级时使用明确摘要和约定退出语义。

### 🔴 校验失败仍返回退出码 0

- **文件**：`src/novel_material/cli/validate.py:17-45,52-72`
- **代码**：

  ```python
  if result:
      console.print("校验通过")
  else:
      console.print("校验失败")
  ```

- **问题**：单素材 `validate`、`quality` 失败及 `--all` 中含失败素材时均退出 0。已复现汇总表含“失败”但命令成功。
- **建议**：单素材失败退出 1；`--all` 只要存在失败项就退出 1，同时保留完整汇总表。

### 🔴 不存在的素材同时显示“目录不存在”和“流水线已完成”

- **文件**：`src/novel_material/cli/pipeline.py:597-609`、`src/novel_material/pipeline/progress.py:185-190`
- **代码**：

  ```python
  print_pipeline_status(progress)  # 打印“素材目录不存在”
  next_stage = get_next_pending_stage(progress)  # 不存在时返回 None
  if not next_stage:
      console.print("流水线已完成")
  ```

- **问题**：已复现 `pipeline status nm_definitely_missing` 输出互相矛盾的信息并退出 0。
- **建议**：`status` 在 `exists=False` 时立即向 stderr 输出并退出非零；不要把“不存在”映射成“无待办阶段”。

### 🔴 Rich 剩余时间会稳定地产生秒级假 ETA

- **文件**：`src/novel_material/cli/pipeline.py:406-411`、`src/novel_material/pipeline/analyze.py:459-472`
- **代码**：

  ```python
  for ch_info in batch:
      # 一个 LLM 批次完成后，10 章在毫秒级连续更新
      progress_callback(total_done, total, desc)
  ```

- **问题**：Rich 默认只用最近 30 秒进度样本。长时间等待 API 后，批内章节瞬间写入，使 Rich 误判处理速度极高；项目描述中已有正确量级的 `ETA ~5h53min`，末尾却再次显示 `0:00:02`。
- **建议**：移除 Rich 的速度 ETA，使用统一的运行计时器；显示带标签的已用时间与基于实际批次耗时计算的剩余时间。

### 🔴 `silent_console` 会隐藏运行中的 ERROR/WARNING

- **文件**：`src/novel_material/infra/progress.py:19-29`、`src/novel_material/infra/logging_config.py:179-213`
- **代码**：

  ```python
  pause_console_logging()
  try:
      yield
  finally:
      resume_console_logging()
  ```

- **问题**：该机制直接移除 pipeline 和 embedding 的全部控制台 handler，不区分级别。已复现上下文内 `logger.error("hidden-error")` 只写文件、终端完全不可见；随后 CLI 仍可能显示绿色完成。
- **建议**：进度运行期间仅抑制低价值 INFO，WARNING/ERROR 通过 Rich `console.log` 或事件汇总安全显示；阶段结束必须输出降级和错误计数。

### 🔴 深度分析“完成”只由文件数量决定

- **文件**：`src/novel_material/pipeline/progress.py:55-67`、`src/novel_material/cli/pipeline.py:539-545`
- **代码**：

  ```python
  return len(list(insights_dir.glob("*.yaml"))) >= total
  ```

- **问题**：失败占位和 schema 无效文件也被终端显示为“✓ 完成”；当前测试素材已验证 1084 个文件中有 90 个无效，但状态仍完成。
- **建议**：终端状态读取明确的阶段结果清单，并区分 `完成/降级/失败/待重试`；不要把“文件存在”当作“内容有效”。

### 🔴 无效用户参数直接暴露 Python/Pydantic traceback

- **文件**：`src/novel_material/cli/pipeline.py:398`、`src/novel_material/cli/search.py:168`
- **代码**：

  ```python
  runtime_mode = get_runtime_mode(mode)  # ValueError
  SearchRequest(...)                    # ValidationError
  ```

- **问题**：已复现非法 `--mode`、`--limit 0`、`candidate-limit < limit` 会打印包含本地绝对路径和第三方库栈的 Rich traceback，而不是 CLI 参数错误。
- **建议**：在 Typer 参数层使用 `Enum`、`min/max` 和回调校验；跨字段错误捕获后转换为 `BadParameter` 或简洁 stderr 消息。

### 🔴 `storage sync` 全量模式无法表达部分或全部失败

- **文件**：`src/novel_material/cli/storage.py:103-113`、`src/novel_material/storage/sync_core.py:168-188`
- **代码**：

  ```python
  count = sync_all(...)
  console.print(f"已同步 {count} 个素材")
  ```

- **问题**：`sync_all` 只返回成功数量；“没有素材”“全部失败”“部分失败”无法区分。已复现返回 0 时显示绿色“已同步 0 个素材”并退出 0。
- **建议**：返回结构化汇总 `{total, succeeded, failed, skipped}`；存在失败时打印明细并退出非零。

### 🔴 删除失败仍返回退出码 0

- **文件**：`src/novel_material/cli/material.py:57-82`
- **代码**：

  ```python
  if result:
      console.print("已删除")
  else:
      console.print("删除失败")
  ```

- **问题**：已复现 `delete_material=False` 时仅打印“删除失败”，退出码仍为 0。破坏性操作尤其需要可靠的成功确认。
- **建议**：删除失败退出 1；未提供 ID 也应作为参数错误退出非零，而不是仅列出素材后正常返回。

### 🔴 所有业务错误都写入 stdout

- **文件**：`src/novel_material/cli/main.py:18`、`src/novel_material/cli/search.py:47-49`、`src/novel_material/infra/logging_config.py:90-93`
- **代码**：

  ```python
  console = Console()
  console.print("[red]检索失败...[/red]")
  logging.StreamHandler(sys.stdout)
  ```

- **问题**：已复现参数错误、数据库错误的 `stderr` 为空，错误文本全部进入 stdout。外部 Agent、Shell 管道和 JSON 消费者无法稳定分离数据与诊断信息。
- **建议**：建立 stdout/stderr 契约：机器结果和正常输出走 stdout，错误与诊断走 stderr；JSON 模式错误输出结构化 JSON 或至少保证 stdout 为空。

### 🔴 进度条把“流程已结束”显示成“数据已成功”

- **文件**：`src/novel_material/pipeline/analyze.py:512-526`、`src/novel_material/cli/pipeline.py:583-590`
- **代码**：

  ```python
  progress_callback(total, total, "分析完成...")
  status = "✓ 完成" if final_progress.get(key) else "○ 未完成"
  ```

- **问题**：进度只有 completed/total 二态，无法表达尝试数、成功数、失败数和降级数；100% 容易被理解为 100% 数据有效。
- **建议**：将进度和结果分离：进度表示“处理完成度”，结果摘要显示成功、降级、失败、待重试数量；阶段状态使用四态模型。

### 🟡 不确定总量任务结束后仍保留旋转图标

- **文件**：`src/novel_material/cli/storage.py:33-40,48-55,65-72,88-95,104-111`、`src/novel_material/cli/pipeline.py:252-271`
- **代码**：

  ```python
  task = progress.add_task("同步全部素材...", total=None)
  progress.update(task, completed=True)
  ```

- **问题**：`total=None` 的 Rich 任务不会因 `completed=True` 变成 finished；已复现最终残留 `⠋ 同步全部素材...` 或 `⠋ 生成大纲...`，随后又打印完成。
- **建议**：显式 `progress.stop_task(task)`，或在结束时设置 `total=1, completed=1`；统一成功、失败终态图标。

### 🟡 分类 ETA 使用固定 45 秒假设

- **文件**：`src/novel_material/cli/material.py:131-133`
- **代码**：

  ```python
  remaining_time_sec = status['remaining'] * 45
  ```

- **问题**：预计剩余时间没有使用历史耗时、模型或重试信息，容易像 Rich ETA 一样长期误导用户。
- **建议**：使用最近 N 个真实任务耗时的稳健统计；样本不足时显示“暂无法估算”。

## 6. 风格

### 🟡 多套终端机制并存

- **文件**：`src/novel_material/infra/progress.py:107-378`、`src/novel_material/cli/pipeline.py:46-878`
- **代码**：

  ```python
  sys.stdout.write("\r...")       # 手工 spinner
  print(...)                       # 原生输出
  Console().print(...)             # Rich 输出
  logging.StreamHandler(sys.stdout)
  ```

- **问题**：手工 spinner、Rich Live、原生 print 和 logging 同时承担终端输出，导致计时模型、换行、重定向和错误显示难以统一。
- **建议**：建立单一 `TerminalReporter`/事件渲染边界；业务层只上报事件，不直接操作终端。

### 🟢 `cli/pipeline.py` 职责和体积过大

- **文件**：`src/novel_material/cli/pipeline.py`（878 行）
- **问题**：参数校验、阶段编排、进度渲染、状态汇总和错误策略全部在同一文件，`full` 与 `continue` 大量复制，修复一处很容易漏另一处。
- **建议**：按“命令适配层、编排服务、终端渲染”拆分；保持服务层不依赖 Rich/Typer。

## 7. 职责边界

### 🔴 CLI 成功语义依赖文件和数据库的二次猜测

- **文件**：`src/novel_material/cli/pipeline.py:570-590`、`src/novel_material/pipeline/progress.py:70-139`
- **代码**：

  ```python
  final_progress = get_pipeline_progress(material_id)
  status = "✓ 完成" if final_progress.get(key) else "○ 未完成"
  ```

- **问题**：CLI 丢弃阶段返回结果，再通过文件存在和数据库查询反推成功状态；查询异常还被吞掉。展示层因此无法解释“为什么失败”或区分环境不可用、未执行、数据无效。
- **建议**：编排层返回结构化 `RunResult`，包含每阶段状态、原因、计数和建议动作；状态查询仅用于历史恢复，不替代当前运行结果。

### 🟡 Rich markup 会解释素材内容中的样式标签

- **文件**：`src/novel_material/cli/search.py:14-35`、`src/novel_material/cli/material.py:177`
- **代码**：

  ```python
  table.add_row(result.document_type, result.title, summary, result.material_id)
  ```

- **问题**：已复现摘要中的 `[red]危险[/red]` 在表格中变成“危险”，标签本身消失。素材标题、摘要和标签属于数据，不应被当作 Rich markup。
- **建议**：对数据单元使用 `Text(value)` 或关闭 markup；只允许代码定义的固定样式。

### 🟡 非交互和窄终端没有统一降级策略

- **文件**：`src/novel_material/cli/main.py:13-26`、`src/novel_material/cli/pipeline.py:46-878`
- **问题**：没有全局 `--quiet`、`--no-progress`、`--no-color` 或统一 JSON 模式；长描述、中文路径、阶段号、ETA 和进度条会争夺有限宽度。管道/CI 仍会收到进度残留行。
- **建议**：按 TTY 自动选择 Rich 交互模式或纯文本事件模式，并提供显式覆盖选项。

## 8. 文档

### 🟡 文档未定义终端契约，且日志路径相互矛盾

- **文件**：`ARCHITECTURE.md:707-715`、`docs/USER_MANUAL.md:339-350`
- **代码/文档**：

  ```text
  ARCHITECTURE: data/novels/{material_id}/pipeline_{date}_{time}_{PID}.log
  USER_MANUAL: 日志位于 logs/
  ```

- **问题**：没有说明退出码、stdout/stderr、进度百分比、降级状态、ETA、非 TTY 和 JSON 错误格式；日志路径也与当前实现不一致。
- **建议**：新增“CLI 输出契约”章节，并统一日志路径、状态语义和故障排查说明。

## 其他已确认问题

### 🟡 错误提示原样显示 `{material_id}`

- **文件**：`src/novel_material/cli/pipeline.py:105,649`
- **代码**：

  ```python
  console.print("[red]请执行：nm pipeline evaluate {material_id}[/red]")
  ```

- **问题**：缺少 `f` 前缀，用户收到不可执行的占位命令。
- **建议**：通过统一的 next-action 渲染器生成真实命令，避免散落字符串模板。

### 🟡 macOS 上 `nm` 与系统 LLVM 工具冲突

- **文件**：`pyproject.toml:40-41`、`README.md:19-55`
- **问题**：当前环境 `command -v nm` 返回 `/usr/bin/nm`，执行的是 LLVM symbol table dumper，而文档全部假设 `nm` 指向项目 CLI。
- **建议**：安装说明中增加 PATH 验证；评估提供不冲突的备用入口名称，并保留 `python -m novel_material.cli.main` 作为诊断入口。

### 🟢 帮助界面中英文混杂

- **文件**：`src/novel_material/cli/main.py:13-26`
- **问题**：命令说明为中文，但 Typer 默认显示 `Usage / Options / Commands / Show this message and exit`；整体体验不统一。
- **建议**：在统一终端层中决定是否完整本地化；优先保证语义和错误契约后再处理文案一致性。

## 建议修复顺序

1. **终端契约**：明确退出码、stdout/stderr、阶段四态与非交互模式。
2. **结果模型**：让编排层返回结构化 `RunResult`，消除展示层二次猜测。
3. **失败语义**：修复 pipeline、validate、storage、material 的错误退出码和失败汇总。
4. **进度组件**：统一 Rich 布局，显示“已用/剩余”，删除 Rich 瞬时速度 ETA。
5. **错误可见性**：进度期间保留 WARNING/ERROR，阶段末展示降级摘要。
6. **参数校验**：把非法输入转换成简洁 CLI 错误，修复无效选项和占位提示。
7. **自动化保障**：补齐 CliRunner 契约测试、TTY/非 TTY 快照测试和窄终端测试。
8. **文档同步**：记录终端契约、日志位置和 macOS 命令冲突处理。

## 审查结论

终端层当前最大风险不是视觉样式，而是**显示结果、退出码、日志状态和真实数据状态之间缺少统一契约**。因此同一运行可能同时出现“失败”“0% spinner”“流水线完成”和退出码 0。建议把终端完善作为独立子项目处理，先建立结果模型和错误语义，再统一进度与视觉呈现。
