# 管道流程问题

## Continue 命令未完成分析

### 问题
使用 `nm pipeline continue` 时，显示章级分析已完成，但实际未完成，任务被忽略。

### 解决
- 修复 meta.yaml 状态读取逻辑
- 正确识别未完成阶段并继续执行

### 相关文件
- `src/novel_material/cli/pipeline.py`

### 归档日期
2026-05-10

---

## 章节字数计算错误

### 问题
章节的 word_count 数值不正确。

### 解决
- 修复字数统计逻辑，正确计算章节字数

### 相关文件
- `src/novel_material/pipeline/stages/ingest.py`

### 归档日期
2026-05-10

---

## 空行保留问题

### 问题
章节分析时保留了原文章节前的空行，但最终输出中空行消失。

### 解决
- 确认空行保留逻辑正确实现
- 输出格式保持原文空行结构

### 相关文件
- `src/novel_material/pipeline/stages/analyze.py`

### 归档日期
2026-05-10

---

## 数据库同步状态确认

### 问题
执行 pipeline 后不确定数据库是否已更新。

### 解决
- 数据库同步阶段添加确认日志
- 显示同步的表和数据量

### 相关文件
- `src/novel_material/pipeline/stages/sync.py`

### 归档日期
2026-05-10

---

## Outline 阶段文件写入延迟

### 问题
Outline 阶段分析过程中没有任何文件写入，担心失败后数据丢失。

### 解决
- 分析过程中写入临时文件
- 完成后写入最终文件
- 添加时间预估信息

### 状态
待优化

### 归档日期
2026-05-10

---

## Outline/Worldbuilding 上下文爆炸问题

### 问题
分析 outline、worldbuilding 时使用 chapters 数据，会不会导致上下文爆炸？

### 解决
- 使用章级摘要池而非完整章节内容
- 控制摘要池大小，限制传入章数
- 大型小说使用滑动窗口提取

### 相关文件
- `src/novel_material/pipeline/stages/outline.py`
- `src/novel_material/pipeline/stages/worldbuilding.py`

### 归档日期
2026-05-10

---

## 全文分析缺失问题

### 问题
没有进行第一步全文分析，流水线和 evaluate.py 有问题。

### 解决
- 修复 evaluate.py 调用逻辑
- 确保全文分析阶段正确执行

### 相关文件
- `src/novel_material/pipeline/stages/evaluate.py`
- `src/novel_material/cli/pipeline.py`

### 归档日期
2026-05-10

---

## continue 命令未自动补全 summary

### 问题
执行 `nm pipeline continue` 时，summary 字数不够的问题没有被自动补全处理。

### 解决
修复 summary 自动重试机制，确保短摘要自动重新生成。

### 相关文件
- src/novel_material/pipeline/analyze.py

### 归档日期
2026-05-12

---

## 校验失败后未重新运行

### 问题
Schema 校验失败后，没有自动重新运行修复，进度条卡在 2%，缺少提示信息。

### 解决
- 修复 validate_material 调用链缺陷
- 修复重分析进度条显示问题
- 添加校验失败的明确提示

### 相关文件
- src/novel_material/cli/validate.py
- src/novel_material/validation/
- src/novel_material/pipeline/progress.py

### 归档日期
2026-05-12

---

## 大纲向量化时机确认

### 问题
大纲生成后没有向量化，向量化出现在精调阶段，精调是否会改动大纲？

### 解决
设计确认：大纲向量化在精调阶段执行是正确设计，精调会基于章级分析数据优化大纲统计信息。

### 相关文件
- src/novel_material/pipeline/outline.py

### 归档日期
2026-05-12

---

## outline 阶段增量写入

### 问题
outline 阶段进度到某点时没有任何文件写入，担心失败后数据丢失，缺少时间预估。

### 解决
- outline/characters 实现增量写入
- 添加断点续传机制
- 增加进度显示和时间预估

### 相关文件
- src/novel_material/pipeline/outline.py
- src/novel_material/cli/pipeline.py

### 归档日期
2026-05-12

---

## evaluation 路径调整

### 问题
evaluation 输出用 meta 包住显得奇怪，是否有大量输出需要这样处理？

### 解决
重构数据库同步模块，调整 evaluation 输出路径，简化输出结构。

### 相关文件
- src/novel_material/pipeline/evaluate.py
- src/novel_material/storage/sync.py

### 归档日期
2026-05-12

---

## run_history.yaml 用途

### 问题
run_history.yaml 是什么？有什么用途？

### 解决
run_history 记录所有 LLM 流水线执行统计，用于追踪 API 调用、耗时、tokens 等运行数据。

### 相关文件
- src/novel_material/cli/pipeline.py
- src/novel_material/pipeline/

### 归档日期
2026-05-12