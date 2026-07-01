# 无人值守流水线质量门与大上下文预算设计

## 1. 背景

2026-07-01 的两次长篇小说流水线事故暴露出同一类系统问题：

- `nm_novel_20260701_7u96` 在 `analyze` 阶段因少量章节持续返回 `pacing: null`，最终缺 3 章并硬失败。
- `nm_novel_20260701_18cb` 虽然 `meta.yaml` 被置为 `finalized`，但 run 状态为 `failed`；世界观为空、核心人物完整小传全失败、insights 大量缺失、profile 缺失，仍然执行了 `sync`。

这些事故说明当前 `pipeline full --mode standard` 的实际语义不清晰：有些低风险字段会拖垮全书，有些高风险空产物却会被包装为成功并继续同步。系统需要从“尽量跑完”改为“质量优先地无人值守完成；不可发布时自动阻断”。

本设计只优化后续系统行为，不修复或补齐已经存在问题的历史素材。历史素材只作为事故样本和回归夹具来源。

## 2. 目标与非目标

### 2.1 目标

- 明确定义 `pipeline full --mode standard` 的发布语义：默认只同步可发布素材。
- 新增 `release_gate` 发布门禁，在 `audit` 后、`sync` 前统一判断是否允许同步。
- 增加 `--allow-degraded-sync` 显式人工放行出口；默认不允许严重降级素材同步。
- 将世界观空结构、核心人物小传全 fallback、profile 缺失等占位兜底从 `success` 中拆出来。
- 在 LLM 输出截断、`finish=length` 或 token 预算不足时，优先扩预算和拆任务，而不是直接降级成功。
- 对 `pacing=None` 这类低风险字段做可追踪字段级恢复，不让少量非核心字段拖垮全书。
- 统一 run 状态、`meta.status`、报告状态和同步状态的口径。
- 保证改动有全局审视：配置层、LLM 调用层、阶段层、编排层、审计层、同步层、报告层和测试层都要覆盖。

### 2.2 非目标

- 不重新分析、修补或同步 `nm_novel_20260701_7u96` 与 `nm_novel_20260701_18cb`。
- 不把 `--allow-degraded-sync` 设计成默认行为。
- 不降低 `standard` 模式质量要求来换取“看起来跑完”。
- 不在本期解决 `evaluation.stage_map` 合并和 `chapter_functions` 受控词表的完整治理；这两个问题进入后续增强包。
- 不改变 embedding 维度，不做数据库大迁移。

## 3. 设计原则

### 3.1 质量优先

质量是第一约束。只要 API 支持足够大的上下文，就不应因保守的 token 上限牺牲世界观、人物小传和作品画像质量。

### 3.2 大上下文优先

当前 API 支持 100 万上下文，因此系统应允许阶段使用更大的输入摘要池和输出预算。预算不足导致的 `finish=length`、JSON 截断、字段缺失应视为配置或任务拆分问题，而不是可静默接受的业务降级。

### 3.3 可发布与可同步分离

`sync success` 只能说明写库动作成功，不能说明素材可发布。发布门禁必须在 `sync` 前给出独立结论。

### 3.4 兜底必须带语义

兜底分两类：

- 可用兜底：低风险字段缺失，经确定性恢复后仍可使用，但需记录质量标记。
- 占位兜底：空世界观、统计人物档案等只能保证流程不崩，不能算阶段成功。

### 3.5 历史事故只做回归，不做修复

设计和实现只改变后续系统行为。对事故素材的验证应使用只读检查、构造夹具或复制到临时目录，不直接修改历史素材。

## 4. 推荐方案

采用“发布门禁 + 阶段语义修正 + 大预算完整性恢复”的方案：

1. 配置层增加质量优先预算档位，允许世界观、人物、profile 使用更大上下文和输出上限。
2. LLM 调用层识别 `finish=length`、JSON 截断和 schema 错误，优先扩输出预算或拆分任务。
3. 阶段层返回结构化 `StageResult`，占位兜底不得映射成 `success`。
4. 编排层新增 `release_gate`，默认阻断严重降级同步。
5. 审计和报告层统一解释质量问题、发布结论和人工放行状态。

这个方案比只改 `pacing` 或只调大 token 更重，但能同时解决硬失败和软失败泄漏，并且符合“保证质量、全局审视”的要求。

## 5. 发布语义

### 5.1 状态定义

`pipeline full --mode standard` 的最终发布语义分三档：

| 档位 | 含义 | 默认能否 sync |
|---|---|---|
| `success` | 核心产物完整，通过审计和发布门禁 | 能 |
| `degraded` | 有可接受缺口，已明确标记，不污染核心检索 | 不能，除非 `--allow-degraded-sync` |
| `failed` | 核心事实缺失、关键阶段失败或严重审计错误 | 不能 |

### 5.2 meta 状态

`meta.status` 不应只表示“流程跑到某一步”，还应避免和 run 状态冲突：

- `analyzed`：章级分析完整，后续增强产物未必完成。
- `finalized`：核心增强产物和审计通过，达到默认可发布状态。
- `degraded`：允许写入一个新状态，用于表示产物存在已知质量缺口。若暂不修改状态枚举，则在 `meta.yaml` 增加 `quality_status: degraded` 和 `release_gate` 摘要。
- `failed`：核心阶段失败或发布门禁失败，禁止默认同步。

实施时优先选择最小兼容方案：保留既有 `status` 枚举，增加 `quality_status` 与 `release_gate` 字段，避免破坏旧读取逻辑。

## 6. CLI 行为

### 6.1 新增参数

在 `pipeline full` 和 `pipeline continue` 增加：

```bash
--allow-degraded-sync
```

语义：

- 默认 `False`。
- 仅当 `release_gate` 判定为 `degraded` 时允许继续 `sync`。
- 若 `release_gate` 判定为 `failed`，该参数不能放行。
- 放行记录必须写入 run report 和 `meta.yaml` 的 `release_gate.override`。

### 6.2 默认行为

默认流程：

```text
ingest -> evaluation -> analyze -> outline -> worldbuilding -> characters
-> tags -> insights -> refine -> profile -> audit -> release_gate -> sync
```

其中：

- `release_gate success`：继续 `sync`。
- `release_gate degraded`：默认停止在门禁阶段，run 状态为 `degraded`，输出提示可用 `--allow-degraded-sync` 人工放行。
- `release_gate failed`：停止，run 状态为 `failed`。

## 7. 大上下文预算设计

### 7.1 配置新增

在 `config/settings.yaml` 增加质量优先预算配置：

```yaml
LLM_CONTEXT_WINDOW_TOKENS: 1000000
LLM_QUALITY_BUDGET_MODE: quality

LLM_WORLDBUILDING_MAX_TOKENS: 64000
LLM_CHARACTERS_MAX_TOKENS: 64000
LLM_PROFILE_MAX_TOKENS: 64000
LLM_INSIGHTS_MAX_TOKENS: 32000

LLM_WORLDBUILDING_SUMMARY_TOKENS: 120000
LLM_CHARACTERS_SUMMARY_TOKENS: 120000
LLM_PROFILE_CONTEXT_TOKENS: 120000
LLM_OUTLINE_SUMMARY_TOKENS: 80000

LLM_LENGTH_RETRY_MULTIPLIER: 2
LLM_LENGTH_RETRY_MAX_TOKENS: 128000
```

默认值可以比上面略保守，但设计上必须支持这些量级。配置服务需要把这些键暴露到 `config["llm"]`。

### 7.2 `finish=length` 策略

LLM 调用层或阶段调用层识别 `finish_reason == "length"` 后，执行以下策略：

1. 如果当前输出预算小于阶段最大上限，按倍数提高 `max_tokens` 后重试。
2. 如果提高预算后仍截断，切换到拆分任务。
3. 若拆分后仍失败，返回结构化诊断，而不是写入 success。

诊断码：

- `llm_output_truncated`
- `llm_budget_expanded`
- `llm_task_split_required`
- `llm_task_split_failed`

### 7.3 任务拆分策略

大对象阶段必须优先拆分，而不是一次生成超大 JSON：

- 世界观：先生成 `overview + dimensions`，再按维度生成实体，最后生成关系。
- 人物：核心人物每批 1-3 人；先生成基础小传，再补心理、关系、弧线。
- Profile：先生成证据索引和结构摘要，再生成可迁移技法与读者期待。
- Insights：批次失败或漏章时自动缩小批次，必要时单章补齐。

## 8. 阶段状态语义修正

### 8.1 worldbuilding

`generate_worldbuilding()` 不再返回裸 `True/False`。改为返回 `StageResult`，至少包含：

```python
outputs={
    "llm_success": bool,
    "entity_count": int,
    "relation_count": int,
    "evidence_count": int,
}
```

状态规则：

- LLM 成功且产物有实体或有效 `not_applicable` 说明：`success`。
- LLM 失败但写入空结构：`degraded` 或 `failed`，由发布策略判定。
- 世界观维度适用但实体/关系/证据全 0：至少 `degraded`。

`run_history` 的 `status` 必须跟 `StageResult.status` 一致，不能硬编码 `success`。

### 8.2 characters

人物阶段输出：

```python
outputs={
    "character_count": int,
    "biography_target_count": int,
    "biography_completed_count": int,
    "biography_failed_count": int,
    "fallback_count": int,
}
```

状态规则：

- 有完整小传目标且完成数为 0：`degraded`，并由 `release_gate` 判定是否阻断。
- 核心人物 LLM 批次 `finish=length` 或超时：先扩预算或拆分；不得直接整批 fallback 成 success。
- fallback 档案可以写入，但必须计入 `fallback_count`。

### 8.3 profile

`generate_work_profile()` 不再裸 `except Exception: return False`。它应返回结构化 `StageResult`：

- `work_profile_api_failed`
- `work_profile_schema_invalid`
- `work_profile_evidence_missing`
- `work_profile_written`

如果 LLM 返回 `finish=stop` 但校验失败，必须记录字段错误摘要。`work_profile.yaml` 缺失在 standard/deep 模式中进入发布门禁。

### 8.4 insights

`insights` 保持增强层定位，但增加成功率阈值：

```yaml
INSIGHTS_MIN_SUCCESS_RATE_STANDARD: 0.8
INSIGHTS_MIN_SUCCESS_RATE_DEEP: 0.95
```

低于阈值：

- 阶段返回 `degraded`。
- `release_gate` 根据模式和缺口决定是否阻断同步。
- 批次失败时先缩小批次或单章补齐。

### 8.5 analyze

`analyze` 保持核心阶段。章节覆盖不完整仍为 `failed`。但低风险字段可以进入字段级恢复。

## 9. 字段级恢复设计

### 9.1 字段分级

章级分析字段分为三类：

| 类别 | 字段 | 行为 |
|---|---|---|
| 硬事实字段 | `summary`、`key_event`、`characters_appear`、`tension_level` | 缺失或非法则重分析，最终仍非法则失败 |
| 可恢复标注字段 | `pacing`、`hook_type`、部分列表标签 | 可确定性 fallback，但必须记录质量标记 |
| 增强字段 | `tension_change`、`emotion_transition`、`plot_progress` | 非 window 模式不阻断；window 模式记录 warning |

### 9.2 `pacing=None`

`pacing` 恢复策略：

1. 若 LLM 返回同义词，继续使用 `normalize_pacing()`。
2. 若为 `None`，根据 `tension_level` 和 `chapter_functions` 推断：
   - 高张力或战斗/冲突类：`快`
   - 低张力或日常/过渡类：`慢`
   - 其他：`中`
3. 在章节结果中写入：

```yaml
quality:
  fallback_fields:
    - pacing
  fallback_reason:
    pacing: "LLM 返回 null，按 tension_level/chapter_functions 推断"
```

4. audit 对该字段给 warning，不给 error。

## 10. release_gate 设计

### 10.1 输入

`release_gate` 读取：

- 当前 run 的 `StageResult` 列表。
- `reports/latest.yaml` 或 audit 结果。
- 关键产物摘要：`chapters.yaml` 覆盖率、`worldbuilding/_index.yaml`、`characters/_index.yaml`、`work_profile.yaml` 是否存在。
- CLI 选项：`mode`、`allow_degraded_sync`。

### 10.2 输出

返回 `StageResult(name="release_gate")`：

```python
outputs={
    "decision": "allow" | "hold" | "block",
    "release_status": "success" | "degraded" | "failed",
    "allow_degraded_sync": bool,
    "reasons": list[str],
}
```

### 10.3 判定规则

默认 `block`：

- `analyze` 失败或章节覆盖不完整。
- 任一核心阶段 `failed` 且不是可选增强层。
- `audit` 有 error。
- `profile` 在 standard/deep 模式缺失。

默认 `hold`，可由 `--allow-degraded-sync` 放行：

- worldbuilding 为空但章节、人物、标签等核心检索仍完整。
- 核心人物小传未全部完成，但已有可用简档。
- insights 成功率低于阈值但不影响核心检索。
- 存在字段级 fallback warning。

默认 `allow`：

- 核心阶段成功。
- audit 无 error。
- 仅有不影响发布的 warning。

### 10.4 sync 接入

`sync` 阶段启用条件从“未传 `--skip-sync`”改为：

```text
not skip_sync and release_gate.outputs.decision == "allow"
```

如果 `release_gate` 为 `hold` 且 `--allow-degraded-sync` 为 true，门禁输出 `decision=allow`，同时记录 `override=true`。

## 11. 审计与报告

### 11.1 Audit severity 调整

审计需要区分：

- `error`：默认阻断发布。
- `warning`：默认 hold 或 allow，取决于发布门禁。
- `info`：仅报告。

建议规则：

- 核心人物完整小传目标为 0/目标数：`error` 或门禁 hold，取决于 standard 承诺。
- 世界观适用维度存在但实体/证据全空：`error`。
- `pacing` fallback：`warning`。
- insights 覆盖低于阈值：`warning` 或 `error`，取决于 mode。

### 11.2 报告新增区块

`reports/latest.md` 增加“发布门禁”区块：

```text
发布状态：degraded
同步决策：hold
人工放行：false
阻断原因：
- worldbuilding_empty
- character_biography_incomplete
建议：
- nm pipeline worldbuilding <id>
- nm pipeline characters <id>
```

如果人工放行：

```text
同步决策：allow
人工放行：true
风险：本次同步包含降级产物
```

## 12. 全局影响面

### 12.1 配置层

修改：

- `config/settings.yaml`
- `src/novel_material/infra/config_service.py`

影响：

- 新增大上下文预算键。
- 保持旧配置可用，缺省值向后兼容。

### 12.2 LLM 调用层

修改：

- `src/novel_material/infra/llm.py`
- 可能新增 `src/novel_material/infra/llm_budget.py`

影响：

- 记录 `finish=length` 诊断。
- 支持阶段级预算扩展。
- 不改变 API Key 和 provider 配置。

### 12.3 Pipeline 阶段层

修改：

- `src/novel_material/pipeline/worldbuilding.py`
- `src/novel_material/pipeline/characters_core.py`
- `src/novel_material/pipeline/characters_layer.py`
- `src/novel_material/pipeline/work_profile.py`
- `src/novel_material/pipeline/insights.py`
- `src/novel_material/pipeline/analyze_validators.py`
- `src/novel_material/pipeline/analyze.py`

影响：

- 逐步减少裸 `True/False` 阶段返回。
- 诊断从泛化 `legacy_stage_failed` 转为阶段专用 code。

### 12.4 编排层

修改：

- `src/novel_material/cli/pipeline_common.py`
- `src/novel_material/pipeline/orchestrator.py` 如需支持动态条件读取前序 stage outputs。
- 新增 `src/novel_material/pipeline/release_gate.py`

影响：

- `sync` 必须受门禁控制。
- `pipeline continue` 也必须经过门禁。

### 12.5 审计与报告层

修改：

- `src/novel_material/audit/*`
- `src/novel_material/reporting/*`

影响：

- 报告展示发布状态和同步决策。
- audit issue severity 和 release gate 判定一致。

### 12.6 存储层

修改：

- `src/novel_material/storage/sync.py`
- `src/novel_material/storage/sync_core.py`

影响：

- `sync` 本身不承担发布判断，但应记录同步时的 release gate 摘要。
- 不需要数据库 schema 迁移时，先写入 run report 和 meta；若后续需要查询降级状态，再单独设计 migration。

## 13. 测试策略

### 13.1 单元测试

新增测试：

- `tests/pipeline/test_release_gate.py`
  - audit error 默认 block。
  - degraded + `allow_degraded_sync=False` 返回 hold。
  - degraded + `allow_degraded_sync=True` 返回 allow 且 override=true。
  - failed 不可被 `allow_degraded_sync` 放行。

- `tests/pipeline/test_analyze_field_fallback.py`
  - `pacing=None` 被恢复并记录 `quality.fallback_fields`。
  - 硬事实字段缺失仍失败。

- `tests/pipeline/test_worldbuilding_stage_result.py`
  - `llm_success=false` 空结构返回 degraded/failed，不是 success。

- `tests/pipeline/test_work_profile_stage_diagnostics.py`
  - schema invalid 返回 `work_profile_schema_invalid`。
  - API 异常返回 `work_profile_api_failed`。

- `tests/pipeline/test_llm_budget.py`
  - `finish=length` 触发预算扩展诊断。
  - 达到最大预算后建议拆分任务。

### 13.2 集成测试

使用构造夹具，不修改历史素材：

- 构造 `7u96` 型夹具：章节分析里 `pacing=None`，验证后续不因该字段硬失败。
- 构造 `18cb` 型夹具：worldbuilding 空、characters fallback、profile 缺失、audit error，验证默认不执行 sync。
- 构造人工放行夹具：degraded 但非 failed，传 `allow_degraded_sync=True` 后允许 sync。

### 13.3 回归验证

历史事故素材只读验证：

- 不运行 LLM 重分析。
- 不写入 `data/novels/nm_novel_20260701_7u96` 或 `data/novels/nm_novel_20260701_18cb`。
- 可以复制必要 YAML 到 `tmp_path` 或测试夹具目录。

## 14. 实施分包

### 包 1：发布门禁与 CLI 参数

目标：

- 新增 `release_gate`。
- 增加 `--allow-degraded-sync`。
- `sync` 受门禁控制。

验收：

- 默认 audit error 不 sync。
- degraded 需人工放行。
- failed 不可放行。

### 包 2：阶段状态语义修正

目标：

- worldbuilding、characters、profile 输出结构化 `StageResult`。
- 空结构、全 fallback、profile schema invalid 不再变成 success 或泛化失败。

验收：

- 对应诊断码可在 reports 中看到。
- `legacy_stage_failed` 不再是 profile 失败的唯一信息。

### 包 3：大上下文预算与截断恢复

目标：

- 增加阶段级大预算配置。
- `finish=length` 自动扩预算。
- 大对象阶段具备拆分入口。

验收：

- 配置服务能读取新键。
- 模拟 length finish 能记录预算扩展。

### 包 4：章级字段恢复

目标：

- `pacing=None` 可恢复。
- 硬事实字段仍严格。

验收：

- 少量 `pacing` 缺失不导致 analyze 整体失败。
- fallback 被 audit/report 追踪。

### 包 5：报告与审计统一

目标：

- reports 展示发布门禁。
- audit severity 与 release gate 一致。
- meta 写入 `quality_status` 和 `release_gate` 摘要。

验收：

- run 状态、meta 状态、报告状态和 sync 状态不再互相冲突。

## 15. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 大预算调用更慢 | 以质量为优先；只在大对象阶段使用，章节批处理仍可保持合理批量 |
| 大输出 JSON 仍截断 | 自动扩预算后切换任务拆分 |
| 门禁过严导致用户无法临时同步 | 提供 `--allow-degraded-sync`，但只放行 degraded |
| 修改状态语义影响旧脚本 | 保持 `RunStatus` 枚举不变，主要通过 `StageResult.outputs` 和诊断码表达细节 |
| meta 新字段影响旧读取 | 新增字段向后兼容，旧读取忽略 |

## 16. 开放决策

当前已确认：

- 采用折中策略：默认阻断严重降级，显式参数允许人工放行 degraded。
- 不修复历史事故素材。
- 优先使用大上下文预算保证质量。

实施前还需在计划中细化：

- `worldbuilding` 空结构在 standard 模式下是 `degraded` 还是 `failed`。建议先返回 `degraded`，由 `release_gate` 根据 audit error 阻断 sync。
- `profile` 是否是 standard 的强承诺产物。建议是强承诺，缺失进入 release gate block。
- insights 覆盖率低于阈值是否阻断 standard sync。建议先 hold，可由人工放行；deep 模式 block。

## 17. 验收定义

本设计完成后的系统应满足：

1. 新素材默认不会在 audit error 存在时自动同步。
2. 降级同步必须显式传入 `--allow-degraded-sync`，并在报告中留下记录。
3. 空世界观、核心人物全 fallback、profile schema invalid 都有结构化诊断。
4. `pacing=None` 不再作为低风险字段拖垮整本书。
5. `finish=length` 不再被视为普通失败；系统会先扩预算或拆任务。
6. run report、meta 和 sync 决策对同一次运行给出一致解释。
7. 所有测试使用夹具或临时目录，不修改历史事故素材。
