# 流线演进实施计划

> 本文档是可执行的实施计划，按阶段划分，每阶段明确目标、输入、输出、改动文件。

---

## 实施阶段总览

| 阶段 | 版本 | 目标 | 状态 |
|------|------|------|------|
| 阶段一 | v2.0.1 | 总体评估流线（分批调用） | 待实现 |
| 阶段二 | v2.0.2 | 滑动窗口章级分析 | 待实现 |
| 阶段三 | v2.1 | key_plot_point/key_event 分离 | ✅ 已完成 |
| 阶段四 | v2.2 | emotional_tone + scene_type 字段 | 待实现 |

---

## 阶段一：总体评估流线

### 目标

在章级分析前，对小说做全局评估，提供类型、主线概要、阶段概要、核心人物提示。

### 输入

- 小说原文（已切分章节）
- 章节总数 N

### 样本策略

| 体量 | 章节范围 | 样本量 | 每份章节 |
|------|----------|--------|----------|
| 小体量 | < 200 章 | 15 章 | 5份 × 3章 |
| 大体量 | ≥ 200 章 | 50 章 | 5份 × 10章 |

### 分批调用流程

```
批次1：第1份样本 → 输出阶段1概要
批次2：第2份样本 + 阶段1概要 → 输出阶段1-2概要
批次3：第3份样本 + 阶段1-2概要 → 输出阶段1-3概要
批次4：第4份样本 + 阶段1-3概要 → 输出阶段1-4概要
批次5：第5份样本 + 阶段1-4概要 → 输出完整评估
```

### 输出

文件：`data/novels/{material_id}/meta/evaluation.yaml`

```yaml
schema_version: "2.1"
novel_type: 修仙
main_thread_summary: "许七安穿越入狱，通过推理破案自救..."  # 200-300字
total_chapters: 912
core_characters_hint: [许七安, 怀庆公主, 许新年, 魏渊, ...]
stage_summaries:
  - {stage: 1, range: "1-182", summary: "破案自救，结识关键人物..."}
  - {stage: 2, range: "183-364", summary: "修炼入门，势力博弈..."}
  - {stage: 3, range: "365-546", summary: "揭开真相，危机逼近..."}
  - {stage: 4, range: "547-728", summary: "高潮战斗，命运抉择..."}
  - {stage: 5, range: "729-912", summary: "结局收束，后续伏笔..."}
evaluation_timestamp: "2026-05-09T10:00:00Z"
```

### 改动文件

| 文件 | 改动内容 |
|------|----------|
| `src/novel_material/pipeline/evaluate.py` | 新增模块：样本选取、分批调用、结果整合 |
| `data/schemas/evaluation.schema.yaml` | 新增 schema 定义 |
| `src/novel_material/cli.py` | 新增命令：`nm evaluate <material_id>` |
| `src/novel_material/pipeline/__init__.py` | 注册 evaluate 模块 |

### 验收标准

1. 小体量小说（100章）评估耗时 < 2分钟
2. 大体量小说（1000章）评估耗时 < 5分钟
3. 输出包含完整的 5 个阶段概要
4. `core_characters_hint` 包含主角和关键配角（≥5人）

---

## 阶段二：滑动窗口章级分析

### 目标

为每章分析提供前后章上下文，输出新增张力变化、情感过渡、主线推进判断。

### 输入

处理第 N 章时：

```yaml
# 全局上下文（阶段一产物）
evaluation: evaluation.yaml

# 上章结果（已完成分析）
prev_chapter: chapters[N-1].yaml 的摘要字段

# 当前章原文
current_chapter: source.txt 第N章

# 下章预览
next_chapter_preview: source.txt 第N+1章前500字
```

### 输出

章级分析新增字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `tension_change` | str | 张力变化（上升/持平/下降/峰值） |
| `emotion_transition` | str | 情感过渡描述（承接→转折→铺垫） |
| `plot_progress` | str | 主线推进（推进主线/支线插曲/喘息） |

### 改动文件

| 文件 | 改动内容 |
|------|----------|
| `src/novel_material/pipeline/analyze.py` | 加载 evaluation + 组装窗口输入 + 解析新增输出 |
| `data/schemas/chapters.schema.yaml` | 新增字段定义 |
| `src/novel_material/storage/sync.py` | 同步新增字段到数据库 |
| `src/novel_material/validation/schema.py` | 校验新增字段 |

### 验收标准

1. 相邻章节张力差值合理（±1，非跳跃）
2. `emotion_transition` 描述与上下章情感连贯
3. `plot_progress` 与 `evaluation.stage_summaries` 对应阶段一致
4. 断点续传：从第 N 章继续时，能加载第 N-1 章结果

---

## 阶段三：key_plot_point/key_event 分离 ✅ 已完成

> 提交：8e123fe feat(chapter): 分离 key_event 与 key_plot_point 字段

### 实现内容

- `key_event`: 关键事件描述，LLM 填充（analyze阶段）
- `key_plot_point`: 结构角色标记，代码推断（refine阶段）
- 新增 `pipeline/infer.py` 结构角色推断模块
- 新增 `infra/constants.py` 存放 KEY_PLOT_POINT_VALUES 常量
- 新增 `scripts/migrate_key_fields.py` 迁移脚本
- 数据库同步、检索支持已更新

---

## 阶段四：新增章级字段

### 目标

扩展章级分析字段，增强检索能力。字段来源于 REQUIREMENTS.md 的真实查询需求。

### 新增字段

| 字段 | 类型 | 优先级 | 标签 |
|------|------|--------|------|
| `emotional_tone` | list[str] | P1 | 情感基调（压抑、悲伤、喜悦、燃、紧张、轻松、悬疑、诡异、温馨、恐惧） |
| `scene_type` | list[str] | P1 | 场景类型（告别、突破、冲突、表白、死亡、战斗、决战、抉择、转变、重逢、背叛、牺牲、反转、内讧、揭秘、危机） |
| `technique` | list[str] | P1 | 叙事技法（闪回、独白、对话驱动、心理推理、细节放大、对比、悬念铺垫） |
| `hook_type` | str | P2 | 章末钩子（悬念钩子、反转钩子、情绪钩子、无钩子） |

### 字段来源推导

| 字段 | 来源需求 | 查询示例 |
|------|----------|----------|
| `emotional_tone` | 需求4情绪型 | "找压抑氛围的章节写法" |
| `scene_type` | 需求4+6场景/事件型 | "找告别场景"、"找突破场景"、"找闪回手法的章节" |
| `technique` | 需求4手法型 | "找对话驱动的章节写法"、"找主角独白的章节" |
| `hook_type` | 需求4特征 | "章节结尾的钩子设计是关键参考" |

### 检索需求映射

| 查询示例 | 检索方式 |
|----------|----------|
| "找压抑氛围的章节" | `emotional_tone: [压抑]` |
| "找告别场景" | `scene_type: [告别]` |
| "找闪回手法的章节" | `technique: [闪回]` |
| "找突破场景" | `scene_type: [突破]` |
| "找对话驱动的章节" | `technique: [对话驱动]` |
| "找决战场景" | `scene_type: [决战]` |
| "找雨中告别" | `scene_type: [告别]` + summary 向量搜索 |

### 改动文件

| 文件 | 改动内容 |
|------|----------|
| `src/novel_material/pipeline/analyze.py` | LLM 输出新增 4 个字段 |
| `data/schemas/chapters.schema.yaml` | 新增字段定义 |
| `data/schemas/tags.yaml` | 新增 4 个维度 |
| `src/novel_material/storage/schema.sql` | 新增列 |
| `src/novel_material/storage/sync.py` | 同步新字段 |
| `src/novel_material/validation/schema.py` | 校验新字段 |

### 验收标准

1. 所有字段从 tags.yaml 选取（P1 字段非自由文本）
2. P1 字段支持多选（list 类型）
3. 检索"告别场景"返回包含 `scene_type: [告别]` 的章节
4. 检索"压抑氛围"返回包含 `emotional_tone: [压抑]` 的章节
5. 检索"闪回手法"返回包含 `technique: [闪回]` 的章节

---

## 执行顺序

```
阶段一（总体评估） ─────┐
                       ├─→ 并行实现
阶段二（滑动窗口） ─────┘
                       ↓
阶段四（新增章级字段）
```

**阶段一、二可并行实现。阶段三已完成。阶段四在阶段二之后实现。**

---

## 相关文档

- [REQUIREMENTS.md](../REQUIREMENTS.md) — 6 个核心检索需求
- [event-unit.schema.yaml](../event-unit.schema.yaml) — 事件级 schema（参考，不做）
- [chapters.schema.yaml](../../data/schemas/chapters.schema.yaml) — 章级 schema 定义