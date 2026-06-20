# 题材感知深度分析

## 1. 为什么需要

`chapters.yaml` 提供稳定的 L1 章级分析，适合主流水线、同步和基础检索。题材感知深度分析新增 L2 输出 `chapter_insights/{chapter}.yaml`，用于提炼更贴近创作机制的参考：核心冲突、读者期待、可复用写法，以及玄幻、仙侠、悬疑等题材的专属推进点。

该层不替代 `chapters.yaml`，也不修改既有章节契约。

## 2. Profile 组合规则

每次分析由多个 profile 合并生成字段契约：

```text
common + 题材 profile + 可选叙事模式 profile
```

第一期只实现：

| Profile | 说明 |
|---------|------|
| `common` | 所有题材共享：核心事件、冲突、读者期待、可复用写法 |
| `xuanhuan` | 玄幻/诸天无限：能力推进、资源收益 |
| `xianxia` | 仙侠：修炼规则、道心/因果选择 |
| `suspense` | 悬疑：线索、信息差、谜题推进 |

默认路由根据 `meta.yaml` 中的题材字段推断，也可用 `--profile` 显式覆盖。

## 3. 输出路径

```text
data/novels/{material_id}/chapter_insights/{chapter:04d}.yaml
```

单章文件包含：

```yaml
schema_version: "1.0"
material_id: "nm_novel_20260101_abcd"
chapter: 1
title: "第1章 开篇"
profiles: ["common", "xuanhuan"]
common:
  core_event: "主角被逐出家族并发现旧戒指异常。"
  conflict: "家族羞辱与主角隐藏机缘之间的冲突。"
  reader_hook: "戒指中的未知传承能否改变主角命运。"
  writing_takeaway: "先压低主角处境，再给出可验证但未完全揭示的机缘。"
genre:
  power_progression: "尚未突破，但建立修炼受阻背景。"
  resource_gain: "获得戒指传承线索。"
evidence:
  - field: "resource_gain"
    source: "chapter_summary"
    text: "主角被逐出家族，戒指出现异常。"
confidence: 0.8
quality:
  repaired: false
  validation_errors: []
```

## 4. CLI

```bash
nm pipeline insights <id> --start 1 --end 10
nm pipeline insights <id> --profile common --profile suspense
nm pipeline full ./novel.txt --mode standard
nm pipeline continue <id> --mode standard
nm validate insights <id>
nm search insight "主角被压制后反杀"
```

## 5. 运行模式

| 模式 | 目标 | 行为 |
|------|------|------|
| `fast` | 先让素材可检索 | 跳过 core insights |
| `standard` | 默认无人值守 | 主流水线 + 批量 core insights |
| `deep` | 质量优先 | core insights + 后续关键章节 deep insights 预留 |

默认配置：

```yaml
PIPELINE_RUN_MODE: standard
LLM_INSIGHT_BATCH_SIZE: 20
INSIGHTS_DEFAULT_DEPTH: core
INSIGHTS_KEY_CHAPTER_RATE: 0.2
PIPELINE_INCLUDE_INSIGHTS: true
PIPELINE_DEEP_INSIGHTS_BLOCKING: false
```

## 6. 如何新增题材 Profile

1. 在 `src/novel_material/analysis_profiles/profiles/` 新增 YAML。
2. 必填字段保持少量，首版建议 2-3 个题材字段。
3. 每个题材必填字段都应能从章级摘要或已有字段找到 evidence。
4. 在 `pipeline/profile_resolver.py` 中加入题材到 profile 的映射。
5. 为 loader、resolver、prompt、validator 增加聚焦测试。

## 7. 质量评估清单

- `field_presence_rate`：期望字段是否存在。
- `keyword_hit_rate`：人工样本关键词是否命中。
- `evidence_presence_rate`：是否有证据。
- `profile_resolution_accuracy`：profile 路由是否正确。
- `repair_rate`：二次修复比例，过高说明字段或 prompt 太难。
- `invalid_after_repair_rate`：修复后仍非法比例。
- `generic_phrase_rate`：是否出现“剧情精彩”等泛化评价。

## 8. 模型能力边界

第一期按 GLM 5.0、Qwen 3.6 Plus 这类中等推理、长上下文但深度分析不保证稳定的模型设计。

- 单章逻辑粒度，不做跨百章因果推理。
- 实现支持多章批量调用，默认批量大小 20。
- 输入只用 `chapters.yaml` 的结构化章级分析，不重新读取整章原文。
- 最多修复 1 次；修复后仍失败也落盘，并记录 `quality.validation_errors`。
- 不使用 LLM judge，先用确定性评估集和人工抽检。
