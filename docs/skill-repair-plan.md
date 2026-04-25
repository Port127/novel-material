# Novel Pipeline Skill 体系修复计划

> **创建时间**：2026-04-22
> **来源对话**：[transcript](../.cursor/projects/Users-kiki-Documents-Project-my-github-novel-novel-material/agent-transcripts/2b69eb24-8707-4a5a-9fb5-43fcafd7fce7/2b69eb24-8707-4a5a-9fb5-43fcafd7fce7.jsonl)
> **案例素材**：`nm_novel_20260422_a1b2`（《三体1》地球往事，36 章，2725 行）
> **说明**：本文是历史修复计划，正文保留创建时的路径与行数记录；当前生效 skill 目录为 `.agents/skills/`，共享约定见 `.agents/skills/_shared/references/skill-conventions.md`。

---

## 目录

1. [背景概述](#1-背景概述)
2. [发现的问题总览](#2-发现的问题总览)
3. [问题详细分析（含原因、后果、相关资料）](#3-问题详细分析)
4. [修复方案（P0/P1/P2 分级）](#4-修复方案)
5. [修改文件清单](#5-修改文件清单)
6. [执行顺序与建议](#6-执行顺序与建议)
7. [修复后验证计划](#7-修复后验证计划)

---

## 1. 背景概述

### 1.1 系统架构

Novel Material 项目是一个小说素材管理系统，核心是一套 **Skill 驱动的流水线**，用于将小说原文自动处理为结构化数据。

整体架构：

```
novel-pipeline（调度器）
  ├── pipeline-ingest     → material-add + source-format（入库 + 格式清洗）
  ├── pipeline-analyze    → outline + worldbuilding + characters + tags（大纲 + 世界观 + 人物 + 标签）
  ├── pipeline-events     → novel-events (all) + build-index（事件拆分 + 索引构建）
  └── pipeline-finalize   → refine + novel-stats（精调 + 统计报告）
```

每个子流水线是独立的 SKILL.md 文件，位于 `.claude/skills/` 目录下。

### 1.2 发生了什么

用户使用 `/novel-pipeline full` 对《三体1》（36 章）执行了完整流水线处理。流水线在流程上全部跑完，最终状态为 `refined`。

但审查发现：**虽然流程完整跑通，产出质量极低**——

- 36 章只产出 **12 个事件**（平均每个事件覆盖 3 章）
- 章节 13-15、26 **完全未被任何事件覆盖**
- 完备性评分 **completeness_score: 0.026**（仅 2.6%）
- 有 **25 个 critical 级遗漏实体**（三体世界 85 次提及、智子 78 次、杨冬 34 次...）
- `backfill_done: false` — AI 补录步骤被跳过
- 尽管如此，pipeline 仍然进入了 `refine` 和 `novel-stats`，**基于残缺数据生成了统计报告**

**此外**：执行过程中触发了 **User API Key Rate limit exceeded** 错误。原因是 agent 在单条消息中并发了大量 Write/StrReplace 调用（例如同时写入 5-6 个 YAML 文件），超过了 API 的速率限制。

### 1.3 核心结论

Skill 体系设计的问题不是「功能缺失」，而是**缺乏质量门控和阻断机制**。流水线是「管道式」的——只要不报错就往下走，不管中间产出的数据质量有多差。

**同时**：SKILL.md 中没有对 AI 的并发写入行为做任何限制，导致 API 速率限制被触发。

---

## 2. 发现的问题总览

按严重程度分为三级：

### P0 — 阻断性问题（不改则系统无意义）

| # | 问题 | 影响范围 | 涉及 Skill |
|---|------|---------|-----------|
| 1 | 阶段间完全没有质量门控 | 所有阶段 | 全部 pipeline- skill |
| 2 | 事件拆分粒度过粗，无最小覆盖密度约束 | events 阶段 | novel-events |
| 3 | ai-backfill 补录机制被跳过，无阻断门 | events → finalize 过渡 | pipeline-events, novel-pipeline |
| 4 | 无 API 速率限制控制，触发 429 错误 | 所有写入密集阶段 | novel-events, novel-worldbuilding, novel-characters, pipeline-events |

### P1 — 重要改进（不改则质量低下）

| # | 问题 | 影响范围 | 涉及 Skill |
|---|------|---------|-----------|
| 4 | outline 产出与事件拆分完全脱节 | analyze → events 过渡 | novel-events |
| 5 | refine 无前置质量门控 | finalize 阶段 | refine, pipeline-finalize |
| 6 | 各 skill 中「批」的概念含义不一致，增加理解难度 | 全文 | 全部 |
| 7 | 上下文控制策略过于模糊，AI 执行不稳定 | 全文 | 全部需读原文的 skill |

### P2 — 优化建议

| # | 问题 | 涉及 Skill |
|---|------|-----------|
| 8 | 缺少事件密度异常检测 | novel-events, quality_audit.py |
| 9 | 缺少跨事件章节重叠度检查 | quality_audit.py |
| 10 | `.bak` 目录管理不规范 | refine |

---

## 3. 问题详细分析

### 问题 1：阶段间完全没有质量门控

**是什么**：流水线各阶段（ingest → analyze → events → finalize）之间没有任何自动质量验证。每个阶段完成后直接进入下一个，不管产出质量。

**为什么发生**：
- Skill 设计中没有在阶段交接处插入 `validate_yaml.py` 等检查
- `novel-pipeline` 调度器只检查「文件是否存在」「状态字段是否为 true」，不检查「数据是否正确」
- 每个 pipeline- skill 内部也没有校验步骤

**怎么发生的（案例）**：
1. `pipeline-analyze` 生成 outline/characters 后，没有运行 `validate_yaml.py`
2. `pipeline-events` 生成 12 个残缺事件后，没有运行覆盖检查
3. `completeness_score` 仅 0.026，但没有任何机制阻止进入 `pipeline-finalize`
4. `refine` 基于残缺事件数据做了「精调」，产出了 `refine_summary: {enrich: 16, adjust: 4}`——但这些操作基于的是不完整的数据

**后果**：流程完整跑通，但产出是**低质量的完整数据**——看起来正确，实际不可用。

**相关资料**：
- `novel-pipeline/SKILL.md` 第 110-131 行（执行子流水线部分，无校验步骤）
- `pipeline-analyze/SKILL.md` 第 52-68 行（执行子 skill 部分，无校验）
- `pipeline-events/SKILL.md` 第 72-86 行（执行事件拆分，无校验）
- `scripts/core/validate_yaml.py`（存在但未在流水线中调用）
- `scripts/core/quality_audit.py`（存在但未在流水线中调用）
- `data/novels/nm_novel_20260422_a1b2/stats.yaml`（`avg_events_per_chapter: 0.33`，密度极低）

---

### 问题 2：事件拆分粒度过粗，无最小覆盖密度约束

**是什么**：`novel-events` SKILL.md 定义「事件 = 一个完整的戏剧动作」，但没有给出**最小覆盖密度**约束，也没有**连续未覆盖章节数的上限**。AI 执行时选择了极度粗糙的粒度。

**为什么发生**：
- SKILL.md 说「事件可能跨越 5-60 章」，给了一个非常宽的范围
- 没有规定「主线连续未被事件覆盖的章节不得超过 N 章」
- 「第四阶段：覆盖检查」只说「检查是否有章节未被覆盖」，但**没有强制要求补处理**

**怎么发生的（案例）**：
- 36 章只产出 12 个事件
- 回忆事件被过度合并：`ev_red_coast_001` 覆盖 8-15 章，`ev_red_coast_002` 覆盖 25-27 章
- 章节 13-15、26 完全空白
- `avg_events_per_chapter: 0.33`，远低于硬科幻应有的密度

**后果**：
- 大量章节内容完全没有被事件标签描述
- 完备性验证发现 25 个 critical 级遗漏
- downstream 所有基于事件数据的操作（refine, stats, search）全部基于残缺数据

**相关资料**：
- `novel-events/SKILL.md` 第 20-72 行（事件单元切分规则，无密度约束）
- `novel-events/SKILL.md` 第 548-568 行（第四阶段覆盖检查，无强制补处理）
- `data/novels/nm_novel_20260422_a1b2/events_manifest.yaml`（12 个事件的章节分布）
- `data/novels/nm_novel_20260422_a1b2/completeness_report.yaml`（38 个遗漏项，25 critical）
- `data/novels/nm_novel_20260422_a1b2/stats.yaml`（`avg_events_per_chapter: 0.33`）

---

### 问题 3：ai-backfill 补录机制被跳过，无阻断门

**是什么**：`pipeline-events` 设计了步骤 7（AI 补录），但实际执行中 AI 跳过了这一步，直接进入了 `pipeline-finalize`。而且**即使有 25 个 critical 遗漏，也没有任何机制阻止流程继续**。

**为什么发生**：
- `pipeline-events` SKILL.md 步骤 7 写道「如果有 critical/warning → 执行 ai-backfill」，但**这不是一个阻断条件**，而是一个建议
- 从 pipeline-events 到 pipeline-finalize 的过渡条件只看 `refined=false/缺失`，不检查 completeness 状态
- `novel-pipeline` 的 continue 模式虽然有兜底检查提到「有 critical + backfill_done=false → 执行 AI 补录」，但**实际执行路径没有走到 continue 模式的这个分支**（因为是从 full 模式连续跑下来的）

**怎么发生的（案例）**：
1. `validate_completeness.py` 输出 25 个 critical
2. AI 看到结果，没有执行 ai-backfill
3. `meta.yaml` 中 `backfill_done: false` 被写入
4. 由于 `refined=false` 缺失，pipeline 判断进入 pipeline-finalize
5. refine 和 novel-stats 基于残缺数据完成

**后果**：补录步骤形同虚设，系统无法自动修复数据质量问题。

**相关资料**：
- `pipeline-events/SKILL.md` 第 170-179 行（步骤 7：AI 补录，无阻断逻辑）
- `pipeline-events/SKILL.md` 第 211-219 行（检查 refined 状态，无 completeness 检查）
- `novel-pipeline/SKILL.md` 第 86-99 行（continue 模式文件系统兜底检查）
- `ai-backfill/SKILL.md`（完整的补录流程设计，但从未被触发）
- `data/novels/nm_novel_20260422_a1b2/meta.yaml`（`backfill_done: false`，`completeness_critical_count: 25`）

---

### 问题 4：无 API 速率限制控制，触发 429 错误

**是什么**：agent 在单条消息中并发了大量 Write/StrReplace 工具调用（最多同时 5-6 个），触发了 `User API Key Rate limit exceeded` 错误。

**为什么发生**：
- 所有 SKILL.md 中都没有对 AI 的并发写入行为做任何限制
- AI 倾向于"批量写入以提高效率"，但每个 Write 工具调用都计为一次 API 请求
- 在事件拆分、世界观生成、人物小传生成等写入密集阶段尤为严重

**怎么发生的（案例）**：
1. transcript 第 66 行：单条消息中同时写了 3 个事件文件（ev_main_003, ev_main_004, ev_game_002）
2. transcript 第 67 行：同时写了 3 个回忆事件文件
3. transcript 第 106-107 行：在修复错误时，单条消息中重写了 5 个事件文件
4. 这些并发写入直接触发了 API 速率限制

**后果**：
- API 调用被拒绝，流水线被迫中断
- 用户需要手动恢复，增加操作成本
- 对于超长小说（500-1000 章），这个问题会更加严重

**相关资料**：
- 对话 transcript 第 1 条消息
- `novel-events/SKILL.md` 第 565-573 行（写入文件部分，无速率限制）
- `novel-worldbuilding/SKILL.md` 第 119-140 行（创建文件夹结构部分，无速率限制）
- `novel-characters/SKILL.md` 第 152-189 行（人物小传写入部分，无速率限制）

---

### 问题 5：outline 产出与事件拆分完全脱节

**是什么**：`novel-outline` 生成了详细的结构分析（3 幕、12 个序列、48 个节拍），但 `novel-events` 在拆分事件时**完全没有引用这些产出**。

**为什么发生**：
- `novel-events` SKILL.md 的第一阶段「线索识别」中，只要求读取 `outline/_index.yaml` 和 `structure.yaml` 的 timelines，但**没有要求将 beat/sequence 作为事件边界的强制参考**
- outline 和 events 是两个独立 skill，设计时假设 AI 会自行关联，但没有强制指令

**怎么发生的（案例）**：
- `outline/structure.yaml` 定义了 48 个 beat，每个 beat 对应一个具体的章节
- 但 events 只产出了 12 个事件，很多 beat 完全没被对应到事件
- outline 的节拍（beat）信息被完全浪费

**后果**：前期分析的高质量产出（outline）没有被利用，事件拆分退化为完全依赖 AI 主观判断。

**相关资料**：
- `novel-events/SKILL.md` 第 351-392 行（第一阶段：线索识别，未强制引用 beat）
- `data/novels/nm_novel_20260422_a1b2/outline/structure.yaml`（48 个 beat 的详细定义）
- `data/novels/nm_novel_20260422_a1b2/outline/_index.yaml`（`beats: 48`）

---

### 问题 6：refine 无前置质量门控

**是什么**：refine 设计为「基于事件数据反哺精调早期产出物」，但没有检查事件数据是否完整就执行了精调。

**为什么发生**：
- `refine` SKILL.md 的前置检查只确认「events 目录下有事件文件」「refine_input.json 存在」，不检查事件覆盖完整性
- `pipeline-finalize` 也没有设置 completeness 阈值

**怎么发生的（案例）**：
- events 只覆盖部分章节，completeness_score 0.026
- refine 仍然执行了 6 个批次的精调
- `refine_summary: {enrich: 16, adjust: 4}` — 基于残缺数据做了「调整」
- 这些调整的价值极低，因为事件数据本身就不完整

**后果**：垃圾进垃圾出。refine 不仅没有提升数据质量，反而在残缺数据的基础上做了可能误导的「精调」。

**相关资料**：
- `refine/SKILL.md` 第 31-42 行（前置检查，无质量门控）
- `pipeline-finalize/SKILL.md` 第 15-20 行（前置检查，无 completeness 检查）
- `data/novels/nm_novel_20260422_a1b2/meta.yaml`（`refined: true`，但基于的是残缺数据）

---

### 问题 7：各 skill 中「批」的概念含义不一致

**是什么**：不同 skill 中「批」的含义完全不同：

| Skill | 「批」的含义 | 大小 |
|-------|-------------|------|
| pipeline-events | 每次处理的一组连续章节 | ~5 章 |
| refine | 每次处理的一组精调任务 | 10 钩子 / 5-10 角色 / 5 对关系 |
| ai-backfill | 每次处理的一组遗漏实体 | 3-5 个实体 |

**为什么发生**：设计时各 skill 独立编写，没有统一的术语表。

**后果**：增加理解和调试难度，新贡献者容易混淆。

**相关资料**：
- `pipeline-events/SKILL.md` 第 82-86 行（`[批次 {n}/{total}] 第 {start}-{end} 章完成`）
- `refine/SKILL.md` 第 136 行（`每次取 10 个钩子进行验证`）
- `ai-backfill/SKILL.md` 第 57 行（`每批处理 3-5 个遗漏实体`）

---

### 问题 8：上下文控制策略过于模糊

**是什么**：所有需要读原文的 skill（novel-outline, novel-characters, novel-events, ai-backfill）都有「分段阅读」策略，但描述模糊。

**为什么发生**：
- SKILL.md 说「≤50 章一次性读取」「分 3-5 段」，但没有规定**每次读取的最大行数**
- 没有禁止性条款（如「禁止一次性读取 >10 章正文」）

**怎么发生的（案例）**：
- `novel-outline` 说 36 章应该「一次性读取」，但 AI 实际执行时分段读取且上下文管理混乱
- 事件拆分时 AI 有时会一次性读取大量章节

**后果**：上下文控制不可预测，可能导致 token 溢出或上下文丢失。

**相关资料**：
- `novel-outline/SKILL.md` 第 24-32 行（上下文控制策略表）
- `novel-characters/SKILL.md` 第 27-35 行（上下文控制策略表）
- `novel-events/SKILL.md` 第 572-580 行（上下文控制策略表）

---

### 问题 9：缺少事件密度异常检测

**是什么**：`quality_audit.py` 只检查单批次内的标签多样性、空字段率等，不检查事件密度是否合理。

**相关资料**：
- `scripts/core/quality_audit.py`（现有审计逻辑，无密度检测）
- `data/novels/nm_novel_20260422_a1b2/stats.yaml`（`avg_events_per_chapter: 0.33`，明显偏低但未被标记）

---

### 问题 10：缺少跨事件章节重叠度检查

**是什么**：`quality_audit.py` 不检查事件对章节的覆盖情况。

**相关资料**：
- `scripts/core/quality_audit.py`（现有审计逻辑，无覆盖检查）
- `data/novels/nm_novel_20260422_a1b2/completeness_report.yaml`（已有覆盖检查结果，但未整合到 quality_audit）

---

### 问题 11：`.bak` 目录管理不规范

**是什么**：refine 备份会留下 `.bak` 目录，多次运行会产生多个备份。

**相关资料**：
- `refine/SKILL.md` 第 102-113 行（备份步骤，无清理旧备份逻辑）
- `data/novels/nm_novel_20260422_a1b2/outline.bak/`（当前案例的备份）
- `data/novels/nm_novel_20260422_a1b2/characters.bak/`（当前案例的备份）

---

## 4. 修复方案

### P0-1：阶段间质量门控

**改哪里**：`novel-pipeline/SKILL.md` + 各 `pipeline-*/SKILL.md`

**怎么改**：

在 `novel-pipeline/SKILL.md` 中新增一个独立章节「质量门控」：

```markdown
## 质量门控（所有模式通用）

每个子流水线完成后必须执行对应的质量检查，检查不通过时**停止流水线并报告**，不进入下一阶段。

| 阶段完成 | 检查项 | 工具 | 通过标准 |
|----------|--------|------|---------|
| pipeline-ingest | YAML schema 校验 | `validate_yaml.py format {id}` | 0 error |
| pipeline-ingest | 章节连续性 | 检查 format_report.yaml | 无缺失章节或用户确认 |
| pipeline-analyze | YAML schema 校验 | `validate_yaml.py outline/worldbuilding/characters/novel-tags {id}` | 0 error |
| pipeline-analyze | 人物名册完整性 | 检查 characters/_index.yaml | protagonist/antagonists 不为空 |
| pipeline-events | YAML schema 抽检 | `validate_yaml.py event {id}` + 随机 3 个事件 | 0 error |
| pipeline-events | 章节覆盖检查 | 扫描 events/*.yaml 的 chapters 字段 | 主线连续未覆盖 ≤ 3 章 |
| pipeline-events | 完备性验证 | `validate_completeness.py {id}` | completeness_score ≥ 0.5 或 backfill_done=true |
| pipeline-finalize | YAML schema 校验 | `validate_yaml.py outline/characters {id}`（精调后） | 0 error |
```

在 `pipeline-ingest/SKILL.md` 的步骤 4 和 5 之间插入：

```markdown
### 4a. 质量检查

```bash
python scripts/core/validate_yaml.py format {material_id}
```

如校验失败，停止并报告具体错误，不进入 source-format。
```

在 `pipeline-analyze/SKILL.md` 的步骤 2 和 3 之间插入：

```markdown
### 2a. 质量检查

依次运行：
```bash
python scripts/core/validate_yaml.py outline {material_id}
python scripts/core/validate_yaml.py worldbuilding {material_id}
python scripts/core/validate_yaml.py characters {material_id}
python scripts/core/validate_yaml.py novel-tags {material_id}
```

任一校验失败，停止并报告。同时检查：
- `characters/_index.yaml` 的 `roster` 中 `protagonists` 和 `antagonists` 不为空
- `outline/_index.yaml` 的 `structure_summary.acts` ≥ 2
```

---

### P0-2：事件最小覆盖密度约束

**改哪里**：`novel-events/SKILL.md`

**怎么改**：

在「事件单元切分规则」部分，在「切分判断标准」之后新增：

```markdown
### 最小覆盖密度约束（硬约束）

为防止事件粒度过粗，必须遵守以下约束：

1. **主线连续未覆盖约束**：主线中连续未被任何事件覆盖的章节数不得超过 **3 章**
   - 扫描所有已生成的事件，找出主线未覆盖的章节
   - 如果发现连续 >3 章没有事件，**必须**在这些章节范围内补切事件
   - 这是**硬约束**，不是建议

2. **参考切分密度**：
   | 小说类型 | 建议主线事件密度 |
   |----------|-----------------|
   | 硬科幻/悬疑 | 每 2-4 章至少 1 个主线事件 |
   | 都市/日常 | 每 3-5 章至少 1 个主线事件 |
   | 奇幻/玄幻 | 每 2-4 章至少 1 个主线事件 |

3. **禁止合并独立场景**：同一章节内两个独立戏剧动作（角色不同、目标不同、结局不同），必须拆分为两个事件

4. **回忆事件不替代主线事件**：回忆/闪回事件只补充背景，不能替代对原文的覆盖
```

同时修改「第四阶段：覆盖检查」（第 548-568 行），将检查改为**强制自动补处理**：

```markdown
### 第四阶段：覆盖检查 + 强制自动补处理

**多线索覆盖规则**：同一章节可被多个事件覆盖。

检查逻辑：
1. 主线应覆盖**所有章节**（每个章节至少被一个主线事件覆盖）
2. 支线只覆盖其涉及的章节（不要求全覆盖）
3. **强制自动补处理**：
   - 计算所有章节中未被任何主线事件覆盖的章节
   - 对缺失章节范围**自动执行补切**，无需用户确认
   - 补切后重新运行覆盖检查，直到全部覆盖
   - 补切时遵循「最小覆盖密度约束」（连续未覆盖 ≤ 3 章）

```
覆盖检查结果：
  第1章: ev_main_001 ✓
  第50章: ev_main_010 + ev_romance_怀庆_001 ✓

  缺失章节：第13,14,15章
  → 自动补处理：ev_main_013（第13-15章）✓

  最终缺失章节：无
```
```

在「质量红线」表格（第 655-666 行）新增：

```markdown
| 11 | 事件密度过低 | 主线 event_count / total_chapters < 0.4 |
```

---

### P0-3：backfill 阻断门

**改哪里**：`pipeline-events/SKILL.md` + `novel-pipeline/SKILL.md`

**怎么改**：

修改 `pipeline-events/SKILL.md` 的步骤 7（第 170-179 行）：

```markdown
### 7. AI 补录（强制阻断门）

运行 `validate_completeness.py` 后，根据结果判断：

**阻断判断表**：
| 条件 | 行为 |
|------|------|
| completeness_score < 0.3 | **强制阻断**：禁止进入 pipeline-finalize，必须执行 ai-backfill |
| completeness_score 0.3-0.5 且 critical_count > 10 | **强制阻断**：必须执行 ai-backfill |
| completeness_score 0.5-0.8 且 critical_count > 0 | **警告**：建议执行 ai-backfill，允许用户选择跳过 |
| completeness_score ≥ 0.8 或 critical_count = 0 | 跳过补录，进入 finalize |

**阻断时的输出**：

```
🚫 数据完整性不足，禁止进入精调阶段

素材：{name}
完备性评分：{score}
遗漏项：critical {n} 项，warning {n} 项

必须执行：/pipeline-events {id}（继续 ai-backfill 补录）
```

**阻断后处理**：
1. 更新 `meta.yaml`：`pipeline.current_stage: "backfill-blocked"`
2. 读取并执行 `ai-backfill/SKILL.md`
3. 每批处理 3-5 个实体，补录完成后重新验证
4. 如果重新验证后 completeness_score ≥ 0.5 且 critical_count ≤ 5，解除阻断
```

修改步骤 8 中的状态检查逻辑（第 211-219 行）：

```markdown
**更新状态后，检查 `meta.yaml` 的 `pipeline.refined` 字段**：
- 如果 `completeness_score < 0.5` 且 `backfill_done=false`
  → **拒绝进入 finalize**，输出阻断信息
- 如果 `refined=false` 或缺失 且 `completeness_score ≥ 0.5` 或 `backfill_done=true`
  → 读取并执行 `pipeline-finalize/SKILL.md`
- 如果 `refined=true` + `refine_hash` 匹配 → 跳过
- 如果 `refined=true` + `refine_hash` 不匹配 → 重新精调
```

在 `novel-pipeline/SKILL.md` 的 continue 模式中，在 Step 1 和 Step 2 之间新增：

```markdown
**Step 1b: 完备性阻断检查**

如果 `completeness_validated=true` 且 `completeness_score < 0.5` 且 `backfill_done=false`：
→ **阻止进入 finalize**，输出阻断信息，建议执行 `/pipeline-events {id}` 进行补录
```

---

### P1-4：outline 与 events 联动

**改哪里**：`novel-events/SKILL.md`

**怎么改**：

在「第一阶段：线索识别」的 1c 之后新增 1d：

```markdown
#### 1d. 读取 outline 节拍作为事件边界参考（强制）

读取 `outline/structure.yaml`，提取所有 `beat` 的章节号和描述。

**这些 beat 是事件拆分的强制参考点**：
- 每个 beat 至少对应一个事件（或作为多事件中的一个主事件的骨架）
- 如果某 beat 覆盖的章节范围内没有事件，**必须补切**
- beat 的 description 可以作为事件 title/summary 的参考素材
```

---

### P1-5：refine 前置质量门控

**改哪里**：`refine/SKILL.md` + `pipeline-finalize/SKILL.md`

**怎么改**：

在 `refine/SKILL.md` 的「前置检查」（第 31-42 行）中增强：

```markdown
## 前置检查（增强版）

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 status 为 `complete` 或 `tagged`
2. 确认 `events/` 目录下有事件文件
3. **检查完备性报告（新增）**：
   - 读取 `completeness_report.yaml`（如存在）
   - 如果 `completeness_score < 0.5` 且 `backfill_done=false`
     → **拒绝执行**：输出「事件数据不完整，请先完成 ai-backfill」
4. **检查章节覆盖率（新增）**：
   - 读取 `chapter_index.yaml` 和所有事件的 `chapters` 字段
   - 如果主线连续未覆盖章节 > 3
     → **警告**：输出「主线覆盖不完整，精调结果可能不准确」
5. 确认 `refine_input.json` 已存在（如不存在，先运行 `extract_refine_data.py`）
6. 确认文件夹结构已存在...（后续不变）
```

---

### P1-6：统一「批」的术语

**改哪里**：`novel-pipeline/SKILL.md`

**怎么改**：在文件顶部（架构章节后）新增：

```markdown
## 术语表

| 术语 | 定义 | 出现位置 |
|------|------|---------|
| **事件批（event batch）** | 每次处理的一组连续章节（通常 3-5 章），产出若干事件 | pipeline-events, novel-events |
| **精调批（refine batch）** | 每次处理的一组精调任务（10 个钩子/5-10 个角色/5 对关系） | refine, pipeline-finalize |
| **补录批（backfill batch）** | 每次处理的一组遗漏实体（3-5 个实体） | ai-backfill, pipeline-events |
```

---

### P1-7：上下文预算约束

**改哪里**：所有需要读原文的 skill

**怎么改**：在每个 skill 中新增统一的上下文预算表：

```markdown
## 上下文预算

| 操作 | 最大读取量 | 说明 |
|------|-----------|------|
| 扫描章节标题 | 不限 | 只读标题行，不读正文 |
| 单章阅读 | 单章全文 | 用于事件拆分/精调 |
| 批量阅读 | ≤ 5 章/次 | 用于 outline 分段阅读 |
| 补录阅读 | ≤ 3 章/次 | 只读遗漏实体相关章节 |

**禁止**：
- 一次性读取 > 10 章正文
- 在不分段的情况下读取全文
- 将上一步的完整输出原样传递到下一步
```

---

### P2-8：事件密度异常检测

**改哪里**：`novel-events/SKILL.md`（质量红线部分）+ `scripts/core/quality_audit.py`

**怎么改**：在 `novel-events/SKILL.md` 质量红线表格新增第 11 行（见 P0-2 的方案）。

在 `quality_audit.py` 中新增 `check_event_density` 函数，检查 `event_count / total_chapters` 比值。

---

### P2-9：章节覆盖检查

**改哪里**：`scripts/core/quality_audit.py`

**怎么改**：新增 `check_chapter_coverage` 函数：

```python
def check_chapter_coverage(events: list, total_chapters: int) -> dict:
    """检查事件对章节的覆盖情况"""
    covered = set()
    for e in events:
        for ch in e.get('chapters', []):
            covered.add(int(ch))

    missing = sorted(set(range(1, total_chapters + 1)) - covered)

    # 计算最大连续缺口
    max_gap = 0
    current_gap = 0
    for i in range(1, total_chapters + 1):
        if i not in covered:
            current_gap += 1
            max_gap = max(max_gap, current_gap)
        else:
            current_gap = 0

    return {
        'covered_chapters': sorted(covered),
        'coverage_rate': round(len(covered) / total_chapters, 3),
        'missing_chapters': missing,
        'max_consecutive_gap': max_gap,
        'status': 'pass' if max_gap <= 3 else 'fail',
    }
```

---

### P2-10：备份清理

**改哪里**：`refine/SKILL.md`

**怎么改**：在步骤 0c（备份步骤）中，先清理旧备份再创建新备份：

```markdown
#### 0c. 备份待修改文件

**先清理旧备份**：
```bash
rm -rf outline.bak/ characters.bak/ worldbuilding.bak/
rm -f tags.yaml.bak
```

**再创建新备份**：
```bash
cp -r outline/ outline.bak/
cp -r characters/ characters.bak/
cp -r worldbuilding/ worldbuilding.bak/
cp tags.yaml tags.yaml.bak
```
```

---

## 5. 修改文件清单

| 优先级 | 文件 | 改动类型 | 预计工作量 |
|--------|------|---------|-----------|
| P0 | `.claude/skills/novel-pipeline/SKILL.md` | 新增：质量门控章节、术语表、阻断检查 | ~15 分钟 |
| P0 | `.claude/skills/pipeline-ingest/SKILL.md` | 新增：质量检查步骤 | ~5 分钟 |
| P0 | `.claude/skills/pipeline-analyze/SKILL.md` | 新增：质量检查步骤 | ~5 分钟 |
| P0 | `.claude/skills/pipeline-events/SKILL.md` | 修改：步骤 7（阻断门）、步骤 8（状态检查） | ~15 分钟 |
| P0 | `.claude/skills/novel-events/SKILL.md` | 新增：最小覆盖密度约束、强制补处理、质量红线 | ~15 分钟 |
| P1 | `.claude/skills/refine/SKILL.md` | 增强：前置检查、备份清理 | ~10 分钟 |
| P1 | `.claude/skills/pipeline-finalize/SKILL.md` | 增强：前置检查 | ~5 分钟 |
| P2 | `scripts/core/quality_audit.py` | 新增：check_chapter_coverage 函数 | ~10 分钟 |

**总计**：约 80 分钟，涉及 8 个文件。

---

## 6. 执行顺序与建议

### 推荐执行顺序

```
第一步：P0-1 质量门控框架（novel-pipeline + pipeline-ingest + pipeline-analyze）
    ↓ 建立基础设施
第二步：P0-2 事件覆盖约束（novel-events）
    ↓ 解决核心问题
第三步：P0-3 backfill 阻断门（pipeline-events + novel-pipeline）
    ↓ 防止问题数据流入 downstream
第四步：P1-4 outline-events 联动（novel-events）
    ↓ 提升事件拆分质量
第五步：P1-5 refine 前置门控（refine + pipeline-finalize）
    ↓ 保护精调阶段
第六步：P1-6 术语统一 + P1-7 上下文预算
    ↓ 可维护性改进
第七步：P2-8/9/10 优化项
    ↓ 锦上添花
```

### 注意事项

1. **每次修改后都应该做语法检查**：确保 YAML 格式正确、markdown 渲染正常
2. **P0 改完后建议先跑一次完整 pipeline**：可以用 `nm_novel_20260422_a1b2` 作为测试对象（先删除其 events/ 和后续产出），验证修改效果
3. **修改 skill 不影响已有数据**：skill 是「指令」，只影响未来的执行，不修改已有文件
4. **质量门控阈值可以调**：文档中的 0.5、0.3、3 章等数值是建议值，后续可根据实际效果调整

---

## 7. 修复后验证计划

修改完成后，按以下步骤验证修复效果：

### 验证 1：质量门控是否生效

**操作**：清理 `nm_novel_20260422_a1b2` 的 events 及后续产出，重新执行 `pipeline-events`

**预期**：
- `validate_yaml.py` 在 analyze 完成后自动运行
- 事件拆分后自动运行覆盖检查
- 如果覆盖率不达标，自动补切事件

### 验证 2：事件覆盖是否改善

**操作**：同上

**预期**：
- 36 章中未覆盖章节 ≤ 3 章连续
- `avg_events_per_chapter` 显著高于 0.33（预期 > 0.5）
- 事件数量显著多于 12（预期 30-50 个）

### 验证 3：backfill 阻断门是否生效

**操作**：在事件拆分后但补录前，检查是否能进入 finalize

**预期**：
- completeness_score < 0.5 时，拒绝进入 finalize
- 输出阻断信息
- 执行 ai-backfill 后，分数提升到 0.5 以上才放行

### 验证 4：outline 与 events 联动

**操作**：检查事件拆分是否引用了 outline 的 beat

**预期**：
- 事件标题/summary 与 beat description 有关联
- beat 覆盖的章节都有对应事件

### 验证 5：refine 前置门控

**操作**：在事件数据不完整的情况下尝试执行 refine

**预期**：
- 如果 completeness_score < 0.5，refine 拒绝执行
- 输出清晰的错误信息

---

## 附录 A：关键数据引用

### 案例数据（nm_novel_20260422_a1b2）

| 文件 | 路径 | 关键数据 |
|------|------|---------|
| 元数据 | `data/novels/nm_novel_20260422_a1b2/meta.yaml` | status: refined, backfill_done: false, completeness_score: 0.026 |
| 格式报告 | `data/novels/nm_novel_20260422_a1b2/format_report.yaml` | 36 章，2933 字符清理 |
| 完备性报告 | `data/novels/nm_novel_20260422_a1b2/completeness_report.yaml` | 38 个遗漏（25 critical, 13 warning） |
| 事件清单 | `data/novels/nm_novel_20260422_a1b2/events_manifest.yaml` | 12 个事件 |
| 事件索引 | `data/novels/nm_novel_20260422_a1b2/events_index.yaml` | 倒排索引 |
| 统计报告 | `data/novels/nm_novel_20260422_a1b2/stats.yaml` | avg_events_per_chapter: 0.33 |
| 全局索引 | `data/index.yaml` | status: refined |

### Skill 文件清单

| Skill | 路径 | 行数 |
|-------|------|------|
| novel-pipeline | `.claude/skills/novel-pipeline/SKILL.md` | 282 |
| pipeline-ingest | `.claude/skills/pipeline-ingest/SKILL.md` | 87 |
| pipeline-analyze | `.claude/skills/pipeline-analyze/SKILL.md` | 114 |
| pipeline-events | `.claude/skills/pipeline-events/SKILL.md` | 260 |
| pipeline-finalize | `.claude/skills/pipeline-finalize/SKILL.md` | 141 |
| novel-events | `.claude/skills/novel-events/SKILL.md` | 735 |
| novel-outline | `.claude/skills/novel-outline/SKILL.md` | 168 |
| novel-characters | `.claude/skills/novel-characters/SKILL.md` | 232 |
| novel-worldbuilding | `.claude/skills/novel-worldbuilding/SKILL.md` | ~200 |
| novel-tags | `.claude/skills/novel-tags/SKILL.md` | 212 |
| refine | `.claude/skills/refine/SKILL.md` | 430 |
| ai-backfill | `.claude/skills/ai-backfill/SKILL.md` | 159 |
| build-index | `.claude/skills/build-index/SKILL.md` | 312 |
| material-add | `.claude/skills/material-add/SKILL.md` | 120 |
| source-format | `.claude/skills/source-format/SKILL.md` | 151 |

### 脚本文件清单

| 脚本 | 路径 | 作用 |
|------|------|------|
| source_format.py | `scripts/core/source_format.py` | 原文格式清洗 |
| validate_yaml.py | `scripts/core/validate_yaml.py` | YAML schema 校验 |
| quality_audit.py | `scripts/core/quality_audit.py` | 事件标注质量审计 |
| build_event_index.py | `scripts/core/build_event_index.py` | 构建 YAML 事件索引 |
| build_db.py | `scripts/core/build_db.py` | 构建 SQLite 数据库 |
| extract_source_entities.py | `scripts/core/extract_source_entities.py` | 从原文提取实体 |
| validate_completeness.py | `scripts/core/validate_completeness.py` | 交叉验证完备性 |
| extract_refine_data.py | `scripts/core/extract_refine_data.py` | 提取精炼统计数据 |
| search.py | `scripts/core/search.py` | 检索脚本 |

---

## 附录 B：历史错误记录

在本次案例执行过程中遇到并修复的错误（这些不是 skill 设计问题，而是执行中的 bug）：

1. **`extract_source_entities.py` AttributeError**：roster 结构是嵌套字典而非简单列表，脚本需要遍历 `roster.values()`
2. **`build_db.py` sqlite3.OperationalError**：旧数据库 schema 冲突，删除 `data/material.db` 重建
3. **事件文件 Schema 验证错误**：所有 12 个事件文件需要修复字段类型（字符串→列表）、补充缺失字段、映射非法标签值
4. **`ev_main_001.yaml` 中 `reader_effect` 字段重复**（第 38-40 行和第 44-46 行各出现一次）
