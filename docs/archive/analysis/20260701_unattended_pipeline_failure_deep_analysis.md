# 2026-07-01 无人值守流水线失败深度分析

> 分析对象：
> - `docs/analysis/nm_novel_20260701_7u96_postmortem.md`
> - `docs/analysis/nm_novel_20260701_18cb_postmortem.md`
>
> 相关素材：
> - `nm_novel_20260701_7u96`：《超神机械师》，1463 章，约 518 万字
> - `nm_novel_20260701_18cb`：《庆余年》，746 章，约 346 万字
>
> 求证材料：
> - `data/novels/*/reports/latest.yaml`
> - `data/novels/*/reports/runs/*.yaml`
> - `data/novels/*/run_history.yaml`
> - `data/novels/*/meta.yaml`
> - `data/novels/*/chapter_index.yaml`
> - `data/novels/*/chapters/`
> - `logs/pipeline_2026-07-01_01-25-37_68677.log`
> - `logs/pipeline_2026-07-01_01-04-10_1982.log`
> - 相关源码：`pipeline/analyze.py`、`pipeline/analyze_validators.py`、`pipeline/worldbuilding.py`、`pipeline/characters_layer.py`、`pipeline/characters_biography.py`、`pipeline/insights.py`、`pipeline/work_profile.py`、`cli/pipeline_common.py`、`pipeline/orchestrator.py`

---

## 一、结论摘要

两份 postmortem 的主要问题判断基本属实，但各自存在需要修正的口径和根因解释：

- `7u96` 的确没有完成无人值守全流程。它在 `analyze` 阶段硬失败，原因是 3 章在初次分析和 3 轮质量重试中持续返回 `pacing: null`，被严格契约校验拒绝，最终只产出 1460/1463 个章节分析文件，后续阶段完全没有执行。
- `18cb` 的问题更危险：它不是早停，而是带着多个已知失败继续向下游推进，最终 `sync` 成功执行。`reports/latest.yaml` 的 run 状态是 `failed`，但 `meta.yaml` 状态是 `finalized`，这说明“素材状态”和“本次无人值守运行状态”已经出现口径分裂。
- 这不是两个孤立故障，而是同一类架构问题的两种表现：LLM 输出不稳定已经被预期到，但阶段契约、阻断策略、兜底策略、审计策略和同步策略没有形成一致的无人值守质量门。
- 当前 `pipeline full --mode standard` 的实际语义不是“无人工介入完成一份可用素材”，而是“尽量跑完并记录部分失败”。这和用户对无人值守的基本预期不一致。

最严重的问题不是单个字段、单次超时或某个 prompt，而是系统没有明确区分三种状态：

1. 可接受成功：产物完整且通过质量门。
2. 可降级成功：产物可用但存在明确、可追踪、不会污染核心检索的数据缺口。
3. 不可发布失败：产物缺关键事实、核心阶段失败、或审计发现严重问题，禁止进入 `finalized` / `sync`。

`7u96` 落在第 3 类，系统硬失败；`18cb` 也落在第 3 类，但系统仍继续同步，这是更值得优先修的地方。

---

## 二、两份 postmortem 属实性判断

### 2.1 `nm_novel_20260701_7u96_postmortem.md`

总体判断：大部分属实，关键证据充分。

已证实内容：

| 原报告判断 | 求证结论 | 证据 |
|---|---|---|
| run 状态为 `failed` | 属实 | `reports/latest.yaml`：`status: failed` |
| 失败阶段为 `analyze` | 属实 | `stages.analyze.status: failed`，诊断码 `stage_unhandled_exception` |
| 1463 章中仅 1460 章成功 | 属实 | `chapter_index.yaml` 有 1463 章；`chapters/` 只有 1460 个文件 |
| 缺失章节为 862、1225、1463 | 属实 | 与 `chapter_index.yaml` 比对，缺失 `[862, 1225, 1463]` |
| 3 章因 `pacing: null` 多轮失败 | 属实 | 日志显示 862、1225、1463 在重试第 1/2/3 轮均报 `chapter_analysis.pacing 应为字符串，实际为 NoneType` |
| 初始阶段还有多章 `pacing=None` | 属实 | 日志中 91、176、269、274、281、337、338、630、1104、1225、1228、1230、1421、1462、1463 等章节均出现该错误 |
| `stage_map` 未合并，33 条 | 属实 | `evaluation.yaml` 中 `stage_map` 数量为 33 |
| `chapter_functions` 严重碎片化 | 属实 | 1460 章共产生 1493 个不同 `chapter_functions` 标签 |
| `meta.genre` 未回填 | 属实 | `meta.yaml` 为 `genre: []`；`evaluation.yaml` 为 `novel_type: [科幻, 游戏, 诸天无限]` |

需要修正或降级为推测的内容：

- “3 章内容结构导致 LLM 遗漏 `pacing`”只能算推测。现有证据只能证明：LLM 多次返回 `pacing: null`，系统将其视为硬契约错误，且没有字段级修复或兜底。是否由章节结构、输出预算、模型行为或 prompt 约束不足导致，需要保留为未证实假设。
- 原报告说“另有 14 章初次分析时出现同样错误”，日志实际可见初始 `schema_invalid` 章节包含 15 个编号，其中有 3 个最终未修复。这个差异不影响主结论，但报告中的数量口径应谨慎。
- 成本字段 `estimated_cost: 2.997159999999999` 属实，但单位不应在报告中直接写死为人民币，除非确认项目成本配置单位。

### 2.2 `nm_novel_20260701_18cb_postmortem.md`

总体判断：问题方向属实，但有两处关键口径需要修正。

已证实内容：

| 原报告判断 | 求证结论 | 证据 |
|---|---|---|
| `meta.yaml` 状态为 `finalized` | 属实 | `meta.status: finalized` |
| 本次 run 有异常 | 属实，而且更严重 | `reports/latest.yaml`：`status: failed` |
| `insights` 降级，43/100 成功 | 属实 | `stages.insights.counts: succeeded=43, failed=57` |
| `profile` 失败 | 属实 | `stages.profile.status: failed`，诊断码 `legacy_stage_failed` |
| `audit` 降级 | 属实 | `stages.audit.status: degraded`，13 个诊断码 |
| 世界观实体、关系、证据均为 0 | 属实 | `worldbuilding/_index.yaml`：`entity_count=0`、`relation_count=0`、`evidence_count=0` |
| 世界观 LLM 提取失败后空结构继续 | 属实 | 日志：`世界观提取 调用失败`、`使用空结构继续，不中断流程` |
| 12 个核心人物完整小传全部失败 | 属实 | `artifact_quality.character_quality`: `biography_target_count=12`、`biography_completed_count=0`、`biography_failed_count=12` |
| 大纲 token 统计为 0 | 属实 | `run_history.yaml`：大纲生成 `api_total: 12`，但 `tokens_in=0`、`tokens_out=0`、`estimated_cost=0.0` |

需要修正的内容：

- 原报告写“流水线状态 finalized”容易误导。准确说法应是：素材 `meta.yaml` 被置为 `finalized`，但本次 `pipeline full` 的 run 状态是 `failed`。这两个状态并存，正是状态系统失真的证据。
- 原报告说“人物小传 LLM 成功返回数据，但 `normalize_biography_response()` 验证失败”。日志显示核心人物批次先 `finish=length`，JSON 解析失败后加大输出预算重试，随后超时，最后走统计兜底。因此人物失败根因不只是 schema 过严，还包括输出截断、JSON 解析失败、超时和兜底后仍标记阶段成功。
- 原报告推测 `profile` 可能是上下文过长或输出限制。日志显示 `作品画像 API` 本身返回 `finish=stop`，但 `work_profile.yaml` 缺失，源码里 `generate_work_profile()` 对调用和 `normalize_work_profile_response()` 使用裸 `except Exception: return False`，没有记录真实异常。因此 `profile` 更可能是响应契约/字段校验失败，但无法从日志直接确认。

---

## 三、逐素材深度分析

### 3.1 `7u96`：硬失败型

运行结果：

| 项目 | 值 |
|---|---:|
| run 状态 | `failed` |
| 成功阶段 | `ingest`、`evaluation` |
| 失败阶段 | `analyze` |
| 总耗时 | 33009.6 秒，约 9.17 小时 |
| API attempts/completed | 254 / 244 |
| token 总量 | 4785746 |
| 章节索引 | 1463 章 |
| 章节分析文件 | 1460 个 |
| 缺失章节 | 862、1225、1463 |

直接失败链路：

```text
LLM 返回章节分析
  -> normalize_chapter_analysis_response()
  -> require_string(result.get("pacing"), "chapter_analysis.pacing")
  -> pacing 为 None，抛出 LLMResponseContractError
  -> 当前章节不写入 chapters/<num>.yaml
  -> 合并 chapters.yaml
  -> run_quality_check() 发现缺失章节
  -> 自动重分析 3 轮
  -> 同样字段再次失败
  -> raise ValueError("章级分析质量校验未通过")
  -> orchestrator 捕获为 stage_unhandled_exception
```

这里的失败不是“没有重试”，而是“重试没有改变失败条件”。系统每次都再次要求 LLM 重新给出完整对象，但没有字段级 repair、没有强制补字段 prompt、没有从相邻章节或原始响应中恢复，也没有带质量标记的安全默认值。结果是单个低信息量字段让全书 518 万字的分析在第 9 小时失败。

更深层的问题：

- `pacing` 对检索和质量有价值，但它不是足以阻断全流程的事实字段。当前契约把它和 `summary`、`key_event` 放在同等硬必填地位，导致风险不成比例。
- `normalize_chapter_analysis_response()` 在任何持久化前执行，这保证不会写入无效章节，但缺少“可修复字段”和“不可修复字段”的分级。
- 质量重试只知道“重跑章节”，不知道“上次失败字段是什么、如何约束模型只修复该字段”。因此 3 轮重试更像重复投掷，而不是确定性修复。

### 3.2 `7u96` 的非致命产物问题

`evaluation.yaml` 已成功产出，但质量明显不适合作为稳定导航层：

- `stage_map` 33 条，来自多个批次直接拼接，存在大量重叠范围。
- `turning_points` 中章节 8 出现 4 次，章节 200 出现 3 次，章节 30、50、80、120、150、180、600 各出现 2 次。
- `analysis_focus` 35 条、`worldbuilding_dimensions` 37 条，均存在语义重复。
- `core_character_candidates` 中存在同一角色不同命名，例如 `韩萧` 与 `韩萧（黑星）`。

`chapter_functions` 标签碎片化也被证实：

| 指标 | 值 |
|---|---:|
| 章节文件数 | 1460 |
| `chapter_functions` 总标注数 | 4402 |
| 独立标签数 | 1493 |
| 高频标签示例 | `伏笔铺设` 88、`势力博弈` 84、`铺垫` 65、`战斗` 63 |

这说明 prompt 中“从字典选取”的约束没有在运行时形成有效受控词表。后续即便 `analyze` 能跑完，标签检索也会被大量近义自由文本稀释。

### 3.3 `18cb`：软失败泄漏型

运行结果：

| 项目 | 值 |
|---|---:|
| `meta.status` | `finalized` |
| run `reports/latest.yaml.status` | `failed` |
| 章节分析 | 746/746 完整 |
| 世界观实体/关系/证据 | 0 / 0 / 0 |
| 核心人物完整小传 | 0/12 |
| insight 成功率 | 43/100 |
| `work_profile.yaml` | 缺失 |
| `sync` 阶段 | success |

这份素材的问题不是“没有跑到最后”。它实际执行到了 `sync`，并把一个质量明显不完整的素材同步到了查询层。

阶段链路如下：

```text
ingest success
evaluation success
analyze success
outline success
worldbuilding success（但 llm_success=false，实体/关系/证据为 0）
characters success（但 12 个核心人物完整小传全失败，fallback 兜底）
tags success
insights degraded（43/100）
refine success
profile failed（work_profile.yaml 缺失）
audit degraded（13 error）
sync success
run 聚合状态 failed
meta 状态 finalized
```

关键矛盾是：run 聚合状态已经是 `failed`，但这并不阻止 `sync`。源码中 `profile` 阶段在 `cli/pipeline_common.py` 被配置为 `blocking=False`；`audit` 虽然是 `blocking=True`，但它返回的是 `DEGRADED` 而不是 `FAILED`，而 orchestrator 只在“blocking 且 `FAILED`”时停止。因此 `audit` 发现严重质量问题后，`sync` 仍然继续。

### 3.4 `18cb` 的世界观失败

日志显示世界观阶段的真实过程：

```text
世界观提取 API ... finish=length
世界观提取 [JSON] 解析失败 ... 加大到 16000，重试 1/2
世界观提取 [TIMEOUT] API 失败
世界观提取 调用失败: Request timed out.
使用空结构继续，不中断流程
世界观提取完成: 维度 11 个，实体 0 个，关系 0 条，证据 0 条
```

源码中 `worldbuilding.py` 在异常后调用 `_empty_layered_worldbuilding()`，并写入 `llm_success=False` 的空结构。这种兜底本身可以接受，但后续又执行：

```python
save_run_history(..., status="success")
return True
```

因此阶段适配器把它映射为 `RunStatus.SUCCESS`。这会制造两个问题：

- 运行层看见的是成功，只有深入产物才知道 `llm_success=false`。
- 下游阶段和 `sync` 不会因为世界观事实为空而停下。

正确行为应至少是 `DEGRADED`，如果该素材的世界观实体是检索核心产物，则应升级为 `FAILED` 并阻断发布。

### 3.5 `18cb` 的人物小传失败

日志显示核心人物阶段失败并非简单 schema 问题：

```text
人物#core批次1 API ... max_tokens=4000 ... finish=length
人物#core批次1 [JSON] 解析失败 ... 加大到 8000，重试 1/2
人物#core批次1 [TIMEOUT] API 失败
批次1 LLM调用失败: Request timed out.
使用出场统计生成基础档案兜底
核心人物: 保存 12 人
```

源码中 `_extract_character_batch()` 捕获所有异常后，为候选人物生成基础档案并继续。最终数据表现为：

| 指标 | 值 |
|---|---:|
| profiles 总数 | 106 |
| `profile_level=brief` | 69 |
| `profile_level=fallback` | 37 |
| `biography_complete=True` | 0 |
| 缺 `arc_summary` | 106 |
| 缺 `psychology` | 106 |

`characters_biography.py` 的完整小传契约确实很重：11 个必填字符串、多组嵌套数组/对象、证据字段、关系字段、心理字段等。对 12 个核心人物一次性生成完整小传，很容易触发输出截断或超时。这里根因是“任务粒度过大 + 输出预算/超时不匹配 + 失败后兜底仍算阶段成功”，而不是单纯的字段校验严格。

### 3.6 `18cb` 的 insights 降级

`reports/latest.yaml` 证实：

| 指标 | 值 |
|---|---:|
| expected | 100 |
| processed | 100 |
| succeeded | 43 |
| failed | 57 |
| `insight_missing_from_batch` | 39 |
| `insight_schema_invalid` | 18 |

日志显示：

- `insights_batch#1` 超时，导致第 1-20 章缺失。
- batch 2-4 有大量 repair 调用，部分成功落盘。
- batch 5 虽然有 API 返回，但只看到第 81 章 repair 成功，82-100 大量缺失。

源码中 `insights.py` 对批次异常的处理是：

```python
except Exception:
    result = {}
...
if failed:
    status = RunStatus.DEGRADED if succeeded else RunStatus.FAILED
```

这解释了为什么 43/100 仍被视为 `DEGRADED` 而不是阻断性失败。对于可选增强层，这可能合理；但如果用户期望 standard 模式产出完整可用素材，`DEGRADED` 必须影响最终发布策略，不能只作为报告里的一个状态。

### 3.7 `18cb` 的 profile 失败与可观测性缺口

日志显示 `作品画像 API` 返回：

```text
作品画像 API: 86.6s ... finish=stop
```

但 `work_profile.yaml` 不存在，报告中只有：

```text
profile: failed
diagnostic_codes: [legacy_stage_failed]
```

源码中 `generate_work_profile()` 如下：

```python
try:
    response = call_llm(...)
    profile = normalize_work_profile_response(...)
except Exception:
    return False
```

这会吞掉最关键的信息：到底是响应不是对象、`evidence_index` 为空、字段类型不匹配，还是其他模型契约错误。由于 `run_profile_stage()` 通过 `adapt_stage_result()` 适配布尔值，最终只能得到泛化的 `legacy_stage_failed`。

这类可观测性缺口会严重拖慢后续修复，因为每次失败后只能重新跑昂贵的 LLM 调用，无法直接定位字段级原因。

---

## 四、共同根因

### 4.1 阶段成功定义不一致

当前各阶段对失败的解释不一致：

| 阶段 | 实际失败 | 当前对外状态 |
|---|---|---|
| `analyze` | 缺 3 章 | `FAILED` |
| `worldbuilding` | LLM 失败，产物为空 | `SUCCESS` |
| `characters` | 12 个核心小传失败，fallback | `SUCCESS` |
| `insights` | 57/100 失败 | `DEGRADED` |
| `profile` | 画像缺失 | `FAILED` |
| `audit` | 13 个 error | `DEGRADED` |
| `sync` | 同步不完整素材 | `SUCCESS` |

这说明系统没有统一回答一个问题：什么叫 `pipeline full` 成功？

如果 `worldbuilding` 为空、核心人物没有完整小传、`profile` 缺失、审计有 13 个 error，仍然可以同步数据库，那么 `sync success` 只代表“写库动作完成”，不代表“写入的数据达到发布质量”。

### 4.2 阻断策略与质量目标脱节

`cli/pipeline_common.py` 中：

- `profile` 是 `blocking=False`。
- `audit` 是 `blocking=True`，但只有 `FAILED` 会阻断；`DEGRADED` 不阻断。
- `sync` 在 `audit` 后执行，只要没有 blocking failed 就继续。

这导致质量审计即使发现 error，也只影响最终 run 聚合状态，不影响同步动作。这与“无人值守跑完全程”的用户预期冲突：无人值守不只是走完步骤，还应该在不可发布时自动停下。

### 4.3 兜底策略没有携带发布语义

兜底有两种：

- 可用兜底：数据仍有可解释价值，只是精度降低。
- 占位兜底：为了不中断流程写入空结构或统计档案，不能视为可发布产物。

当前系统没有区分二者。`worldbuilding` 空结构和核心人物 fallback 都属于占位兜底，但阶段仍成功。审计虽然能发现问题，却没有阻止后续同步。

### 4.4 LLM 输出预算和任务粒度不匹配

`18cb` 中多处 `finish=length` 后重试，再超时：

- 世界观提取：`finish=length`，JSON 解析失败，重试后超时。
- 核心人物小传：`finish=length`，JSON 解析失败，重试后超时。
- 配角批次也出现 `finish=length`。

这说明大对象生成任务已经超过稳定输出边界。单纯提高 `max_tokens` 会增加耗时和超时概率，不是稳定方案。更可靠的方向是拆分任务、减少每次输出对象数量、先生成骨架再逐项补全。

### 4.5 契约严格化缺少分级修复

`7u96` 的 `pacing` 问题说明：严格契约可以保护数据质量，但如果没有分级修复，低风险字段也会成为全流程阻断点。

需要区分：

- 事实核心字段：`summary`、`key_event`、`characters_appear` 等，缺失应阻断或重修。
- 分类/标注字段：`pacing`、`hook_type`、部分标签字段，可字段级 repair 或带质量标记兜底。
- 增强字段：不应阻断核心入库，但应影响增强层状态和发布等级。

### 4.6 可观测性不足

最典型的是 `work_profile.py` 裸 `except`。它把昂贵的 LLM 响应、字段错误和真实异常全部压成 `False`，再被适配为 `legacy_stage_failed`。这会让后续 postmortem 只能猜。

类似问题还包括：

- `worldbuilding.py` run history 状态硬编码为 `success`。
- 大纲生成阶段 token 统计为 0。
- 部分 run 状态、素材状态、报告状态之间缺少明确映射说明。

---

## 五、为什么“无人值守跑完全程”失效

用户期望的无人值守至少包含四层含义：

1. 命令不会因为可修复的小字段失败而崩溃。
2. 如果产物不可用，系统必须清楚失败并停止发布。
3. 如果产物可降级，系统必须明确降级范围和后续修复动作。
4. 最终状态、报告状态、数据库同步状态不能互相打架。

当前系统在两端都失效：

- `7u96` 对可修复字段过于刚性，导致全流程早死。
- `18cb` 对不可发布产物过于宽松，导致失败数据继续同步。

所以这不是“要更宽松”或“要更严格”的单选题。真正需要的是分层质量门：

```text
字段级契约
  -> 字段级 repair / safe fallback
  -> 阶段级完整性判定
  -> 产物级审计
  -> 发布级阻断策略
  -> sync 前最终门禁
```

现在系统有字段契约、有审计、有报告，但中间缺少一致的状态传播和发布门禁。

---

## 六、修复建议

### P0：重新定义 `pipeline full` 的成功和同步门禁

建议把 standard/deep 模式的发布规则写成显式策略：

- 任一 blocking 核心阶段 `FAILED`：停止后续发布阶段。
- `audit` 出现 error：默认禁止 `sync`，除非用户显式 `--allow-degraded-sync`。
- `worldbuilding.llm_success=false` 且实体/关系/证据全为 0：至少 `DEGRADED`；如果 standard 模式要求世界观可检索，则 `FAILED`。
- `characters.biography_target_count > 0` 且 `biography_completed_count=0`：至少 `DEGRADED`；如果核心人物小传是 standard 承诺产物，则 `FAILED`。
- `profile` 缺失：若 standard 模式承诺作品画像，则阻断 `sync`；否则从 standard 承诺中移除。

### P0：修复 `pacing=None` 的字段级恢复

不建议简单把所有 `pacing=None` 静默改成 `中`。更稳妥的策略：

1. `normalize_chapter_analysis_response()` 保持识别错误，但将错误分类为可修复字段错误。
2. 对 `pacing` 单字段执行 deterministic fallback：优先从 LLM 原始文本、相邻章节张力变化、章节功能推断；无法推断时填入默认值并记录 `quality.fallback_fields: ["pacing"]`。
3. 对 fallback 章节加入审计 warning，但不让 3/1463 的低风险字段阻断全书。
4. 测试覆盖：`pacing=None` 的章节应能落盘，且质量报告能标记 fallback。

### P0：禁止空世界观以 success 进入下游

修改方向：

- `worldbuilding.py` 的 `save_run_history(status=...)` 根据 `layered.index.llm_success` 写入 `success/degraded/failed`。
- `run_worldbuilding_stage()` 不应只根据 `return True` 判定成功，最好直接返回 `StageResult`，携带 `entity_count`、`relation_count`、`evidence_count` 和 `llm_success`。
- 空结构允许写入，但必须是 degraded/failed 产物，不能伪装为成功。

### P1：拆分核心人物完整小传

当前一次生成 12 人完整小传风险过高。建议改为：

- 每次 1-3 个核心人物。
- 第一轮只生成基础小传和证据索引。
- 第二轮补心理、关系、弧线。
- 每个人独立落盘，失败只影响该人物，不让一批 12 人全部 fallback。
- fallback 档案必须显式 `profile_level=fallback`，并让 characters 阶段返回 degraded。

### P1：修复 `work_profile` 可观测性

`generate_work_profile()` 不应裸 `except Exception: return False`。至少应：

- 捕获 `call_llm` 异常并记录 API/timeout/json 诊断。
- 捕获 `normalize_work_profile_response()` 异常并记录字段错误摘要。
- 返回 `StageResult`，不要经由布尔适配器丢失信息。
- 保留失败响应片段或结构化错误路径，方便复盘。

### P1：调整 insights 降级阈值

如果 `insights` 是 standard 模式承诺产物，43/100 不应只是普通 degraded。建议：

- 配置 `min_success_rate`，例如 standard 至少 80%。
- 低于阈值返回 `FAILED` 或 `DEGRADED_BLOCKING`。
- 批次超时后自动缩小 batch size，而不是整批记 missing。
- 对 batch 返回漏章执行单章补齐。

### P1：建立受控 `chapter_functions` 词表

`7u96` 的 1493 个独立标签证明 prompt 约束不足。建议：

- 将合法 `chapter_functions` 放入配置/字典。
- normalize 阶段做映射和拒绝。
- 对未知标签进入候选审核，不直接污染章节文件。
- 同义归并：如 `伏笔铺设`/`伏笔埋设`、`战斗高潮`/`高潮战斗`。

### P2：合并 evaluation 导航产物

评估批次输出不应直接拼接：

- `stage_map` 合并为非重叠或少重叠的全局阶段。
- `turning_points` 按章节去重。
- `core_character_candidates` 做别名归并。
- `analysis_focus` 和 `worldbuilding_dimensions` 做语义去重。
- 将 `evaluation.novel_type` 回填或映射到 `meta.genre`，但要避免覆盖人工分类。

### P2：修复 telemetry

大纲生成有 12 次 API 调用但 token 全为 0，说明阶段级 telemetry 没有正确采集或归属。建议：

- 所有 LLM 调用统一通过同一 telemetry 入口。
- 阶段开始前记录 baseline，阶段结束只计算增量。
- run_history、reports/latest.yaml、日志三方使用同一数据源。

---

## 七、建议验收标准

后续修复完成后，至少用这两份素材做回归：

### `7u96` 回归标准

- `nm pipeline continue nm_novel_20260701_7u96 --mode standard` 能从 `analyze` 缺口继续。
- 862、1225、1463 均生成章节文件。
- fallback 字段可在质量报告中追踪。
- 后续 outline/worldbuilding/characters/tags/insights/refine/profile/audit/sync 的执行策略符合新的质量门。
- 最终 run 状态与 `meta.status` 不冲突。

### `18cb` 回归标准

- 如果世界观仍为空，run 不得显示 worldbuilding success。
- 如果 12 个核心人物小传仍失败，characters 或 audit 必须阻断 sync，除非显式允许降级同步。
- `profile` 失败时报告必须包含真实字段错误或解析错误。
- `sync` 不得在 audit error 未处理时默认执行。
- `work_profile.yaml` 存在且通过模型校验，或 standard 模式明确不承诺该产物。

---

## 八、最终判断

两份旧 analysis 的问题大方向属实：这次无人值守流水线确实出现了严重退化。

但更准确的判断是：

- `7u96` 暴露的是“严格契约缺少字段级恢复”，导致大体成功的章级分析无法跨过最后 3 章。
- `18cb` 暴露的是“阶段兜底和发布门禁失联”，导致世界观为空、核心人物小传全失败、insights 大量缺失、profile 缺失的素材仍然执行了同步。

因此修复重点不应只盯单点 prompt 或某个字段，而要优先统一 `StageResult` 语义、审计阻断策略和 `sync` 前质量门。否则下次可能表现为不同字段、不同阶段、不同小说，但本质仍是同一个问题：系统没有可靠地区分“跑完了”和“产物可用”。
