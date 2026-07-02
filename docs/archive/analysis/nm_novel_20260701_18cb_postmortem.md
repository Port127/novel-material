# 复盘分析报告：素材 `nm_novel_20260701_18cb`（庆余年）

## 一、分析概述

| 项目 | 内容 |
|---|---|
| 素材 ID | `nm_novel_20260701_18cb` |
| 素材名称 | 0030_庆余年 |
| 章节数 | 746 章 |
| 字数 | 3,464,650（约 346 万字） |
| 分析时间 | 2026-07-01 |
| 流水线状态 | finalized（但存在多项异常） |

---

## 二、分析过程回顾

### 第一阶段：初步状态检查

通过 `nm pipeline status` 和 `meta.yaml` 获取素材基本信息，发现：
- 核心阶段（ingest → sync）大部分成功
- 3 个阶段异常：`insights` 降级、`profile` 失败、`audit` 降级

### 第二阶段：Reports 深度分析

读取 `reports/latest.yaml` 和 `reports/latest.md`，发现：
- 总耗时 5.3 小时，Token 消耗 289 万，成本 $1.86
- 产物质量审计：13 个 error，2 个 warning
- 12 个核心角色全部缺少完整小传

### 第三阶段：根因追溯

通过检查源代码（`insights.py`, `characters_layer.py`, `work_profile.py`, `worldbuilding.py`）和运行日志（`run_history.yaml`, `runs/*.json`），定位到 5 个具体异常。

### 第四阶段：系统性异常排查

全面检查数据文件（`worldbuilding/`, `characters/`, `chapter_insights/`, `outline/`），结合代码逻辑和日志交叉验证，确认异常根因。

---

## 三、发现的异常

### 异常 1：Worldbuilding 数据完全为空 ⛔ 严重

**现象**：
- `entity_count: 0`, `relation_count: 0`, `evidence_count: 0`
- `worldbuilding/entities/` 目录为空
- `overview.yaml` 明确记录 `limitations: ['LLM 世界观提取失败']`

**根因**：
- 唯一的 LLM 调用失败（`api_error_rate: 100.0`）
- 代码 `worldbuilding.py:269` 硬编码了 `status="success"`，将失败掩盖

**代码位置**：
```python
# worldbuilding.py:242-273
except Exception as e:
    layered = _empty_layered_worldbuilding(dimension_routing)
# ...
save_run_history(
    status="success"  # ← 硬编码，无论 LLM 是否成功
)
return True  # ← 永远返回成功
```

**影响**：世界观维度识别了 11 个类别，但没有实体、关系和证据，检索时无法返回具体信息。

---

### 异常 2：人物小传全部失败 ⛔ 严重

**现象**：
- 12 个核心角色（范闲、庆帝、林婉儿等）全部 `biography_complete: false`
- 档案级别为 `fallback`，缺少 `arc_summary`, `psychology`, `relationships`

**根因**：
- 核心人物 12 人只有 1 次 API 调用，LLM 成功返回了数据
- 但 `normalize_biography_response()` 验证失败（JSON 不符合 11 个必填字段 + 7 个嵌套结构的要求）
- 异常被 `_extract_character_batch` 捕获，使用统计兜底档案

**Prompt 复杂度**：
```
必填字段（11 个字符串）：
identity, life_summary, external_goal, internal_need, fear,
fatal_flaw, contradiction, speech_style, description, arc_summary,
narrative_function

复杂嵌套结构（7 个）：
arc_stages, relationships, key_scenes, craft_notes,
psychology, key_events, habits + interaction_patterns
```

**影响**：核心角色缺少成长弧线、心理描写和深度关系网络。

---

### 异常 3：Insights 批次级失败 ⚠️ 中等

**现象**：
- 只处理了 100 章（采样模式），成功 43 章，失败 57 章
- **Batch 1（章节 1-20）和 Batch 5（章节 82-100）整批次失败**
- 18 章 schema 验证失败（repair 后仍有 2-10 项错误）

**根因**：
- `insights.py:186-188` 中，LLM 调用失败时 `result = {}`
- 批次 1 和 5 的 LLM 调用完全失败（可能是超时或 token 超限）
- 另外 18 章的 LLM 输出质量不稳定，schema 验证失败

**数据分布**：
```
成功文件：43 个（章节 21-81，10 个连续段）
失败批次：Batch 1（20章），Batch 5（19章）
Schema 错误：18 章（28, 30, 40-43, 47-48, 50-51, 59, 68, 72-73, 75-78）
```

**影响**：43% 的采样章节缺少深度分析。

---

### 异常 4：Profile 阶段失败 ⚠️ 中等

**现象**：
- `legacy_stage_failed` - 阶段返回了 `False`
- 耗时 87 秒

**根因**：
- `work_profile.py:43-44` 中，LLM 调用或解析时抛出异常
- Profile 阶段需要整合所有章节摘要 + 大纲 + 人物 + 世界观 + 标签
- Prompt 可能超过 LLM 上下文窗口或输出限制

**影响**：缺少 `work_profile.yaml`（作品级写作入口）。

---

### 异常 5：大纲生成 Token 统计为 0 ℹ️ 轻微

**现象**：
- 12 次 API 调用但 `tokens_in: 0`, `tokens_out: 0`, `estimated_cost: 0.0`

**根因**：
- Telemetry 没有正确记录 token 消耗（`telemetry.details` 中的字段为空）
- 阶段本身成功（大纲完整：4 acts, 10 sequences, 91 beats）

**影响**：无法准确统计成本。

---

## 四、数据完整性评估

| 数据类别 | 完整度 | 状态 |
|---|---|---|
| 章节分析 (chapters.yaml) | 746/746 (100%) | ✅ 完整 |
| 章节向量 (chapter_embeddings) | 746/746 (100%) | ✅ 完整 |
| 大纲 (outline) | 4 acts, 10 seqs, 91 beats | ✅ 完整 |
| 标签 (tags) | 完整 | ✅ 完整 |
| 人物档案 (characters) | 106 人（12 核心降级） | ⚠️ 部分降级 |
| 章节洞察 (chapter_insights) | 43/100 (43%) | ⚠️ 采样不完整 |
| 世界观 (worldbuilding) | 0 实体, 0 关系 | ❌ 完全为空 |
| 作品画像 (work_profile) | 缺失 | ❌ 未生成 |

---

## 五、根因归类

| 根因类型 | 涉及异常 | 说明 |
|---|---|---|
| **代码 Bug** | 异常 1, 异常 5 | 失败标记为 success、token 统计缺失 |
| **Prompt 复杂度过高** | 异常 2 | 人物小传 schema 要求过于复杂，LLM 难以稳定返回 |
| **LLM 调用失败** | 异常 1, 异常 3, 异常 4 | 超时、token 超限或 JSON 解析错误 |
| **LLM 输出质量不稳定** | 异常 3 | 批次返回漏章、schema 验证失败 |
| **设计问题** | 异常 3 | Insights 只采样 100 章，覆盖率不足 |

---

## 六、建议修复方案

### 高优先级

1. **修复 Worldbuilding 状态标记**
   ```python
   # worldbuilding.py:269
   status="success" if layered.index.llm_success else "failed"
   ```

2. **简化人物小传 Schema**
   - 将 11 个必填字段减少到 5 个核心字段
   - 分多次 LLM 调用逐步填充（如先填基础信息，再填心理描写，最后填关系网络）
   - 或降低 `profile_level` 要求，允许 `brief` 级别作为可接受结果

3. **增加 Insights 重试机制**
   - 批次失败时自动重试 1-2 次
   - 减小 `insight_batch_size`（如从 20 降到 10）

### 中优先级

4. **Profile 阶段拆分**
   - 将 prompt 拆分为多个子任务（章节摘要、大纲、人物、世界观分别处理）
   - 或增加 `profile_timeout` 配置

5. **Token 统计修复**
   - 检查 `telemetry.details` 中 token 字段的来源
   - 确保 `call_llm` 正确记录 token 消耗

### 低优先级

6. **Insights 覆盖率提升**
   - 考虑将采样比例从 100 章提升到 200-300 章
   - 或改为按 `analysis_focus` 动态选择章节

---

## 七、经验教训

1. **LLM 调用必须有完善的降级策略**
   - Worldbuilding 的降级策略（空结构兜底）合理，但状态标记错误掩盖了问题
   - Characters 的降级策略（统计兜底）导致数据质量下降

2. **Prompt 复杂度需要控制**
   - 人物小传的 11 个必填字段 + 7 个嵌套结构过于复杂
   - 应该分步骤、分层次构建 prompt

3. **批量处理需要考虑 LLM 的可靠性**
   - Insights 的批次失败说明 LLM 在长上下文下的注意力衰减问题
   - 需要减小批次大小或增加重试机制

4. **状态标记必须准确反映实际情况**
   - Worldbuilding 的 `status="success"` 硬编码是典型的反模式
   - 应该根据实际结果动态设置状态

5. **Token 统计是成本管控的基础**
   - Token 统计为 0 会导致成本无法追踪
   - 需要确保 telemetry 的完整性

---

## 八、后续行动

1. **立即修复**：Worldbuilding 状态标记 bug
2. **短期优化**：简化人物小传 schema，增加 insights 重试
3. **中期改进**：拆分 profile 阶段，提升 insights 覆盖率
4. **长期规划**：建立 LLM 调用的质量监控和自动修复机制

---

**报告生成时间**：2026-07-01
**分析工具**：nm-material skill, nm CLI, 源代码审查
**数据来源**：`reports/latest.yaml`, `run_history.yaml`, `runs/*.json`, 各阶段数据文件
