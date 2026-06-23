# LLM 响应契约定向审查报告

**日期**：2026-06-23  
**范围**：`src/novel_material/` 中全部 `call_llm()` 业务消费点  
**语言**：Python 3.10+  
**问题总数**：7（🔴 5，🟡 2，🟢 0）

## 解决状态（2026-06-24）

本报告中的 5 个 Critical 与 2 个 Suggestion 已完成代码修复：

- 新增统一 `LLMResponseContractError` 及对象、数组、字符串、整数、数值契约原语。
- 世界观、单章分析、大纲前提、标签和素材分类均在首次消费响应前校验结构。
- 总体评估、大纲分幕、beats 和人物提取保留既有降级策略，并将结构错误标记为 `schema_invalid`。
- insights、搜索重排和审计复核继续使用原有成熟验证器。

验证结果：

- `pytest -q tests/infra/test_llm_contracts.py`：`5 passed`。
- LLM 响应契约与分类定向测试：`22 passed`。
- `pytest -q`：`363 passed, 1 skipped`。

## 摘要

| 维度 | Critical | Suggestion | Nice to have | 合计 |
|---|---:|---:|---:|---:|
| 命名 | 0 | 0 | 0 | 0 |
| 格式 | 0 | 0 | 0 | 0 |
| 未使用引用 | 0 | 0 | 0 | 0 |
| 注释 | 0 | 0 | 0 | 0 |
| 逻辑 | 4 | 1 | 0 | 5 |
| 风格 | 0 | 0 | 0 | 0 |
| 职责边界 | 1 | 1 | 0 | 2 |
| 文档 | 0 | 0 | 0 | 0 |
| **合计** | **5** | **2** | **0** | **7** |

本次只审查“LLM JSON 已解析，但业务层是否验证顶层和嵌套字段类型”，未发现与该问题相关的命名、格式、引用、注释和文档缺陷。

## 自动检查与复现

- `rg -n "call_llm\\(" src/novel_material --glob '*.py'`：定位 15 个业务调用点。
- 静态追踪每个调用点从 `call_llm()` 返回值到校验、遍历、落盘或数据库写入的完整路径。
- 使用项目 Python 环境注入畸形返回值，不调用外部 API；确认以下最小复现：
  - 单章分析顶层数组：`AttributeError: 'list' object has no attribute 'get'`。
  - 大纲前提顶层数组：`AttributeError: 'list' object has no attribute 'get'`。
  - 标签顶层数组：`AttributeError: 'list' object has no attribute 'get'`。
  - 分类结果 `quality: []`：`AttributeError: 'list' object has no attribute 'get'`。
  - 总体评估顶层数组：`AttributeError: 'list' object has no attribute 'get'`。
  - 大纲幕序列或 beats 返回标量：`AttributeError: 'str' object has no attribute 'get'`。
- 未运行全量测试：本轮按 Code Review 约束只生成报告，没有修改生产代码。

## 1. 逻辑

### 🔴 世界观仅捕获 API 异常，响应结构异常发生在容错范围之外

- **文件**：`src/novel_material/pipeline/worldbuilding.py:203-226`
- **问题**：提示词允许不存在的维度返回空数组，业务代码却把 `power_system`、`geography`、`lore` 固定当作对象并链式调用 `.get()`。本次真实运行已由 `power_system: []` 类响应触发崩溃。
- **建议**：修正提示词的字段级空值契约，在 API 返回与落盘之间执行纯函数归一化和严格类型校验，并把结构校验纳入阶段错误处理。

### 🔴 单章分析在 API 调用成功后才验证结构，畸形对象会逃出单章降级逻辑

- **文件**：`src/novel_material/pipeline/analyze.py:392-452`、`src/novel_material/pipeline/analyze_validators.py:58-93`
- **问题**：`try/except` 只包住 `analyze_chapter()`；顶层数组、字符串张力值或其他错误字段类型会在 `_validate_chapter_analysis()`、窗口校验或结果赋值时抛出异常，直接中断章级分析阶段，而不是把当前章记录为失败并继续。
- **建议**：在 `analyze_chapter()` 返回边界先验证顶层对象，再对摘要、张力、列表字段归一化或返回明确 schema 错误；验证和保存必须处于单章错误隔离范围内。

### 🔴 大纲前提提炼把未校验结果传出容错范围

- **文件**：`src/novel_material/pipeline/outline_logic.py:76-98,422-433`、`src/novel_material/pipeline/outline_io.py:64-77`
- **问题**：`extract_premise()` 只捕获 API 异常，成功解析的顶层数组会原样返回；随后 `save_meta_with_premise()` 和阶段统计调用 `.get()` 并崩溃，默认前提兜底不会生效。
- **建议**：在 `extract_premise()` 内验证并归一化完整前提契约，结构错误与 API 错误共用默认值兜底。

### 🔴 标签生成在数据库操作前未验证顶层及集合字段

- **文件**：`src/novel_material/pipeline/tags.py:111-164,235-324`
- **问题**：标签 API 调用的 `try/except` 在 `validate_and_save_tags()` 之前结束。顶层非对象会直接崩溃；`genre_primary`、自由标签等字段的错误集合类型还可能在数据库循环中异常或产生无意义候选值。
- **建议**：数据库连接前完成响应契约验证；只允许明确的字符串、字符串数组和可空标量，结构错误进入默认标签兜底，禁止边校验边写数据库。

### 🔴 素材分类只检查顶层对象，嵌套 `quality` 未校验且异常类型未被捕获

- **文件**：`src/novel_material/material/classify.py:158-238,312-324`
- **问题**：`parse_classification_result()` 会验证顶层字典，但直接对 `quality` 调用 `.get()`，且分数未验证为数值。调用方只捕获 `ValueError`，因此 `quality: []` 产生的 `AttributeError` 会逃出预期失败结果。
- **建议**：完整验证 `quality` 对象及其数值字段，并将所有契约错误统一转换为领域 `ValueError` 或专用异常。

## 2. 职责边界

### 🟡 总体评估依赖上层捕获类型异常，缺少本地契约边界

- **文件**：`src/novel_material/pipeline/evaluate.py:249-293,403-417`
- **问题**：`evaluate_batch()` 直接假设顶层对象及 `novel_type/core_characters_hint` 为数组。畸形结果会被 `run_evaluation()` 捕获并返回失败，不会形成原始 traceback，但整个总体评估阶段终止，丢失可诊断的字段级错误。
- **建议**：在批次函数内验证响应并返回明确诊断，使调用方能区分 API 失败与 schema 失败。

### 🟡 大纲分幕、beats 与人物提取只有形状兼容，没有显式字段契约

- **文件**：`src/novel_material/pipeline/outline_acts.py:95-104`、`src/novel_material/pipeline/outline_beats.py:92-98`、`src/novel_material/pipeline/characters_layer.py:154-183`
- **问题**：这些入口兼容“裸数组或对象包裹数组”，但没有校验数组元素及嵌套字段。异常通常会被上层捕获并使用简单大纲、跳过 beats 或统计档案兜底，因此不会中断全流水线，却会把结构错误误记为笼统的“LLM 调用失败”。
- **建议**：增加各自的轻量契约函数，保留现有兜底，同时记录 `schema_invalid` 而非 API 错误。

## 已具备较好防护的入口

- `pipeline/insights.py`：使用 `_coerce_items()`、字段验证和 repair 后复验。
- `search/rerank.py`：使用 `_validate_rankings()` 严格检查顶层、条目、ID、分数和覆盖范围。
- `audit/reviewer.py`：通过 `ReviewDecision.model_validate()` 校验完整模型。
- `material/classify.py`：已校验顶层对象，但仍存在上述嵌套 `quality` 缺口。

## 建议修复顺序

1. 世界观、单章分析、大纲前提、标签、素材分类：修复会逃出局部容错的高风险边界。
2. 总体评估：将整阶段失败改为可诊断的 schema 失败。
3. 大纲分幕、beats、人物提取：统一诊断语义并细化字段校验。
4. 将成熟模式沉淀为“每个业务响应一个显式契约”，不要在通用 `call_llm()` 中硬编码所有业务 schema。
