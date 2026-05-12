# 日志系统优化

## 日志基础信息缺失

### 问题
日志只有启动信息，没有小说简介、tokens、输入输出时间、耗时等有效信息，无法分析问题。

### 解决
- 日志添加小说名称、章数、总字数
- API 调用记录：输入字数、输出字数、thinking tokens、finish_reason、request_id
- 批次统计：摘要平均字数、张力范围、解析耗时

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志警告缺失

### 问题
日志里没有警告信息，所有警告只在终端显示，无法追溯问题。

### 解决
- WARNING 级别日志写入文件
- 保持终端与日志文件内容同步

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志文件数量过多

### 问题
一次运行产生多个日志文件，管理混乱。

### 解决
- 每次运行产生一个日志文件
- 文件名包含日期和 PID：`pipeline_YYYY-MM-DD_{pid}.log`

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志内容只有启动信息

### 问题
日志只有启动信息，没有其他内容，出现问题无法分析。

### 解决
- 记录完整处理过程
- 包含小说信息、API调用、错误详情等

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志缺少小说简介信息

### 问题
日志里没有小说简介，不知道在处理哪本小说，缺少 tokens、耗时等关键信息。

### 解决
- 启动时记录小说名称、章数、字数
- API调用记录 tokens、耗时、finish_reason
- 批次统计摘要字数、张力范围

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 警告未写入日志

### 问题
骨架分析、人物提取等脚本的进度输出未写入日志文件。

### 解决
- 统一使用 pipeline logger
- 所有子模块日志都写入同一日志文件

### 相关文件
- `src/novel_material/pipeline/progress.py`
- `src/novel_material/pipeline/stages/*.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志警告缺失

### 问题
日志里没有警告信息，所有警告只在终端显示，无法追溯问题。

### 解决
- WARNING 级别日志写入文件
- 保持终端与日志文件内容同步

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志文件数量过多

### 问题
一次运行产生多个日志文件，管理混乱。

### 解决
- 每次运行产生一个日志文件
- 文件名包含日期和 PID：`pipeline_YYYY-MM-DD_{pid}.log`

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志内容只有启动信息

### 问题
日志只有启动信息，没有其他内容，出现问题无法分析。

### 解决
- 记录完整处理过程
- 包含小说信息、API调用、错误详情等

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志缺少小说简介信息

### 问题
日志里没有小说简介，不知道在处理哪本小说，缺少 tokens、耗时等关键信息。

### 解决
- 启动时记录小说名称、章数、字数
- API调用记录 tokens、耗时、finish_reason
- 批次统计摘要字数、张力范围

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志文件并发写入

### 问题
同时运行两个解析程序会写入同一个日志文件，导致日志混乱无法分析。

### 解决
- 日志文件名包含进程 PID：`pipeline_YYYY-MM-DD_{pid}.log`
- 每个进程独立日志文件

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志警告缺失

### 问题
日志里没有警告信息，所有警告只在终端显示，无法追溯问题。

### 解决
- WARNING 级别日志写入文件
- 保持终端与日志文件内容同步

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志文件数量过多

### 问题
一次运行产生多个日志文件，管理混乱。

### 解决
- 每次运行产生一个日志文件
- 文件名包含日期和 PID：`pipeline_YYYY-MM-DD_{pid}.log`

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志内容只有启动信息

### 问题
日志只有启动信息，没有其他内容，出现问题无法分析。

### 解决
- 记录完整处理过程
- 包含小说信息、API调用、错误详情等

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志缺少小说简介信息

### 问题
日志里没有小说简介，不知道在处理哪本小说，缺少 tokens、耗时等关键信息。

### 解决
- 启动时记录小说名称、章数、字数
- API调用记录 tokens、耗时、finish_reason
- 批次统计摘要字数、张力范围

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志空行与切分策略

### 问题
日志中出现大量空行和 warning，需要规范切分策略。

### 解决
- 按日期生成日志文件
- 大小切分作为备选方案（暂未实现）
- 空行问题需进一步排查

### 状态
部分解决，空行问题待追踪

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志警告缺失

### 问题
日志里没有警告信息，所有警告只在终端显示，无法追溯问题。

### 解决
- WARNING 级别日志写入文件
- 保持终端与日志文件内容同步

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志文件数量过多

### 问题
一次运行产生多个日志文件，管理混乱。

### 解决
- 每次运行产生一个日志文件
- 文件名包含日期和 PID：`pipeline_YYYY-MM-DD_{pid}.log`

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志内容只有启动信息

### 问题
日志只有启动信息，没有其他内容，出现问题无法分析。

### 解决
- 记录完整处理过程
- 包含小说信息、API调用、错误详情等

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志缺少小说简介信息

### 问题
日志里没有小说简介，不知道在处理哪本小说，缺少 tokens、耗时等关键信息。

### 解决
- 启动时记录小说名称、章数、字数
- API调用记录 tokens、耗时、finish_reason
- 批次统计摘要字数、张力范围

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## API 日志格式优化

### 问题
API 调用日志分散在多行，信息重复：

```
[INFO] 批次[1-10] 输入: 21952 字符 | 平均 2195 字/章 | 10 章
[INFO] [章节分析#批次[1-10]] API: 48.8s | in=14216 out=2651 ...
[INFO] 批次[1-10] 统计: 返回 10/10 章 | 摘要平均 75 字 ...
```

期望合并为紧凑格式。

### 解决
优化为：
```
[INFO] [nm_novel_xxx] 批次[1-10] API: 48.8s | in=14216 out=2651 | thinking=1035
[INFO] [nm_novel_xxx] 批次[1-10] 完成: 10/10 章 | 摘要=75字 | 张力=2-4
```

### 状态
已优化，格式更紧凑

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志警告缺失

### 问题
日志里没有警告信息，所有警告只在终端显示，无法追溯问题。

### 解决
- WARNING 级别日志写入文件
- 保持终端与日志文件内容同步

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志文件数量过多

### 问题
一次运行产生多个日志文件，管理混乱。

### 解决
- 每次运行产生一个日志文件
- 文件名包含日期和 PID：`pipeline_YYYY-MM-DD_{pid}.log`

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志内容只有启动信息

### 问题
日志只有启动信息，没有其他内容，出现问题无法分析。

### 解决
- 记录完整处理过程
- 包含小说信息、API调用、错误详情等

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## 日志缺少小说简介信息

### 问题
日志里没有小说简介，不知道在处理哪本小说，缺少 tokens、耗时等关键信息。

### 解决
- 启动时记录小说名称、章数、字数
- API调用记录 tokens、耗时、finish_reason
- 批次统计摘要字数、张力范围

### 相关文件
- `src/novel_material/pipeline/progress.py`

### 归档日期
2026-05-10

---

## continue 命令日志缺失

### 问题
执行 `nm pipeline continue nm_novel_20260510_y4fz` 时没有日志输出，无法判断是 continue 命令本身没有日志还是 outline 阶段没有日志。

### 解决
日志文件名加上时分秒便于排序，解决日志查找困难问题。

### 相关文件
- src/novel_material/infra/llm.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12