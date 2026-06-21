# Golden Query 候选补足设计

**状态：** 待用户书面审阅  
**日期：** 2026-06-21  
**范围：** 仅影响 `nm eval search prepare` 生成的人工标注池

## 1. 问题与目标

当前精确候选导出会严格应用 Golden Query 的结构化过滤条件。真实运行中，30 条查询有 7 条不足 10 个候选，其中 3 条没有结果，无法满足“每个 case 至少标注 10 个候选”的阶段门槛。

本设计在不修改 Golden Query、不改变精确检索评分语义的前提下，为人工标注池补足候选。`nm eval search score --mode exact` 继续使用原始查询和原始过滤条件，补足候选不得进入精确基线的结果列表。

## 2. 方案

候选准备分两步：

1. 使用原始查询和全部过滤条件执行严格检索。
2. 严格结果少于目标数量时，使用相同查询移除结构化过滤条件再次检索，并按 `result_id` 去重补足。

严格结果始终排在放宽结果之前。补足达到目标数量后停止；放宽检索仍不足时保留实际结果，并继续输出 `no_candidates` 或不足数量状态，禁止复制结果凑数。

每条候选增加：

- `candidate_source: strict`：来自原始查询与过滤条件。
- `candidate_source: relaxed`：来自移除过滤条件的补足检索。

候选的 `relevance` 仍初始化为 `null`，只允许人工填写 0～3 分。

## 3. 组件边界与数据流

- `src/novel_material/eval/search_eval.py`：只负责合并严格候选和放宽候选、去重、来源标记与 YAML 输出；不理解具体文档类型。
- `src/novel_material/cli/eval.py`：提供严格检索和放宽检索调用。放宽检索通过创建 `filters={}` 的临时 `SearchEvalCase` 实现，不修改输入查询文件。
- `eval/search_queries.yaml`：保持不变，继续保存真实业务查询、原始过滤条件和人工 judgments。
- `eval/search_candidates.yaml`：人工工作文件，记录候选来源；不作为精确评分输入。

数据流：

```text
Golden Query
  ├─ 原始 filters ─→ strict candidates ─┐
  └─ filters={} ───→ relaxed candidates ├─→ 按 result_id 去重 → 标注池
                                         ┘
```

## 4. 错误与边界处理

- 严格检索异常：候选准备失败并非零退出，不用放宽结果掩盖故障。
- 严格检索成功但数量不足：执行放宽检索。
- 放宽检索异常：候选准备失败并非零退出，避免生成不可复现的部分标注池。
- 严格结果已达到目标数量：不得执行放宽检索。
- 相同 `result_id` 同时出现在两路：只保留严格结果并标记为 `strict`。
- 两路合计仍不足：输出实际结果；零结果 case 保留 `status: no_candidates`。
- 标签导入仍拒绝 `null`、未知结果和没有候选的 case。

## 5. 验证与验收

自动化测试覆盖：

1. 严格结果足够时不调用放宽检索。
2. 严格结果不足时调用放宽检索并补足目标数量。
3. 严格结果优先，跨路按 `result_id` 去重。
4. YAML 正确记录 `candidate_source`。
5. 查询文件内容不被修改。
6. `score --mode exact` 不读取 `search_candidates.yaml`，评分语义保持不变。
7. 全量单测不低于当前 `97 passed, 1 skipped`。

真实候选导出完成后统计 30 个 case：目标是每个 case 至少 10 条真实候选；若底层实体总量不足 10 条，则记录实际数量并作为数据覆盖缺口报告，不复制或伪造候选。
