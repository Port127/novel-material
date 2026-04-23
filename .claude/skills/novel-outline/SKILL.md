---
name: novel-outline
description: 读取小说原文，生成故事大纲（文件夹结构：结构、节奏、钩子网络）
when_to_use: 用户想要为入库小说生成大纲骨架
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

读取小说原文，生成文件夹结构的故事大纲。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/novels/{material_id}/meta.yaml`
3. 读取 `data/novels/{material_id}/source.txt`

## Schema

输出遵循 `docs/schemas/outline.schema.yaml` 的文件夹结构。

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

## 上下文控制策略

长篇小说采用**分段阅读 + 增量汇总**：

| 小说规模 | 策略 | 每段大小 |
|----------|------|----------|
| ≤ 50 章 | 一次性读取 | 全文 |
| 51-300 章 | 分 3-5 段 | 约 50-100 章/段 |
| > 300 章 | 分 5-10 段 | 约 80-150 章/段 |

**段边界优先对齐卷/幕分界**（如果原文有明确的卷划分）。

## 执行步骤

### 1. 扫描章节结构

读取 `source.txt`，**仅扫描章节标题行**，建立章节索引：
- 总章数、各章标题、有无明确的卷/幕分界
- 据此确定分段方案

如果存在 `chapter_index.yaml`，直接复用。

### 2. 分段阅读 + 提取

对每一段：

#### 2a. 读取本段原文

按章节索引定位，只读当前段的章节文本。

#### 2b. 提取本段要素

- **结构骨架**：本段覆盖哪个叙事阶段，核心事件，转折点
- **情节线索**：本段推进了哪些情节线
- **钩子**：本段埋设或回收了哪些钩子（记录章节号 + 描述）
- **节奏感知**：标注本段内关键章节的 tension（1-5）
- **时间线**：是否存在多线叙事、闪回、时间跳转

每段产出**段落笔记**（内存中，不写文件）。

#### 2c. 进入下一段

段间只传递段落笔记的压缩摘要，控制上下文累积。

### 3. 汇总合成

所有段落笔记收集完毕后，综合生成全书大纲。

#### 3a. 确定启用模块

根据小说特征判断启用哪些可选模块：

| 模块 | 启用条件 |
|------|----------|
| `plotlines.yaml` | 多线叙事（timeline_count > 1） |
| `hooks_network.yaml` | 钩子数量 > 10 |
| `pacing_curve.yaml` | 章节数 > 30 |
| `subplots.yaml` | 支线数量 > 3 |
| `themes.yaml` | 主题复杂度判断 |
| `emotional_arc.yaml` | 情绪导向判断 |

#### 3b. 提取结构骨架

按幕/序列/节拍划分：
- 每幕覆盖的章节范围
- 幕内序列划分
- 序列内节拍标注
- 主要叙事弧线
- 核心事件
- 转折点
- 节奏特征

#### 3c. 识别结构模板

判断小说结构类型（三幕式、英雄之旅、五幕式、环形结构等）。

#### 3d. 整合钩子网络（如启用）

合并各段的钩子记录，匹配埋设点和回收点：
- 标注铆合形式（反转/悬念/因果/期待）
- 标注未回收的钩子

#### 3e. 生成节奏曲线（如启用）

选取关键章节，生成张力曲线。

#### 3f. 整合情节线索（如启用）

识别各情节线索，标注起点→转折→高潮→收束。

#### 3g. 建立线索交汇锚点（如启用 plotlines 或 subplots）

当识别到多线叙事时，**建立主线与支线/感情线的初始交汇锚点**，为后续事件拆分提供参考：

- 在 `plotlines.yaml` 的 `intersections_with` 字段中标注线索间交汇关系
- 在 `subplots.yaml` 的 `relation_to_mainline` 字段中标注支线与主线的关系类型
  （`parallel` 并行 / `intertwining` 交织 / `counterpoint` 对照 / `framing` 框架）
- 在 `subplots.yaml` 的 `mainline_integration` 中预估交汇章节

**示例**：
```yaml
# outline/subplots.yaml — novel-outline 阶段产出（预估）
subplots:
  - name: "魏渊个人线"
    relation_to_mainline: intertwining  # 预估关系类型
    ...

mainline_integration:
  - subplot: 魏渊个人线
    anchor_chapters: [100, 250]  # 基于大纲推断的预估交汇章
    integration_type: causal     # 预估交汇类型
```

> ⚠️ 此阶段的交汇锚点是**大纲级别的推断**，不保证准确。
> 精确的交汇点在 pipeline-events 第五阶段通过事件级数据捕捉，在 refine batch-2b 中验证。

### 4. 写入文件夹结构

创建 `data/novels/{material_id}/outline/` 文件夹，写入：

```
outline/
├── _index.yaml              # 概览 + 模块索引 + 统计
├── structure.yaml           # 必选：结构骨架
├── plotlines.yaml           # 可选（如启用）
├── hooks_network.yaml       # 可选（如启用）
├── pacing_curve.yaml        # 可选（如启用）
├── subplots.yaml            # 可选（如启用）
├── themes.yaml              # 可选（如启用）
└── emotional_arc.yaml       # 可选（如启用）
```

**注意**：本阶段识别的钩子写入 `hooks_network.yaml` 的初步版本，refine 阶段会补充详细验证。

**⚠️ API 速率限制约束（硬约束）**：

为防止触发 API Key Rate Limit，文件写入必须遵守以下限制：

| 规则 | 说明 |
|------|------|
| **单次消息最多 2 个 Write 调用** | 一次响应中最多并行写入 2 个文件 |
| **每个大纲模块独立写入** | 写完一个文件后，确认完成再写下一个 |

**执行策略**：先写 `_index.yaml` → 再写 `structure.yaml`（必选，最大文件）→ 然后每次最多 2 个可选模块。

### 5. 更新状态

将 `meta.yaml` 中 `status` 更新为 `outlined`（如果当前是 `raw`）。

## 输出格式

```
✅ 大纲已生成（文件夹结构）

📚 素材：{name}
📁 目录：data/novels/{id}/outline/
🏗️ 结构：{N}幕 {M}序列 {K}节拍
📈 启用模块：{modules列表}
📊 钩子：{H}条（初步识别，refine阶段详细验证）

文件列表：
  - _index.yaml（概览）
  - structure.yaml（结构骨架）✓ 必选
  - {其他启用的模块}.yaml ✓ 可选

后续步骤：
  /novel-worldbuilding {id}  # 提取世界观设定
```

## 注意事项

- 大纲是全书骨架，采用文件夹结构支持模块化
- `structure.yaml` 是必选模块，其他模块根据特征自动启用
- premise 用一句话概括核心前提
- 钩子只记录主要的，不需要穷举
- 短篇（≤50 章）可一次性读取，无需分段
- 段落笔记只保留结构性信息，不摘抄原文
- 各模块写入遵循 `docs/schemas/outline.schema.yaml` 格式

## References

- [outline.schema.yaml](../../../docs/schemas/outline.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)