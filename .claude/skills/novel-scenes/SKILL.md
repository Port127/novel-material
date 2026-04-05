---
name: novel-scenes
description: 将小说按场景拆分，为每个场景打多维标签（支持分批执行和全书自动处理）
when_to_use: 用户想要拆分小说场景并打标签
argument-hint: "[material_id] [章节范围 | all | all:批次大小]"
arguments: material_id, chapter_range
---

# 任务

将小说按场景拆分，为每个场景生成多维标签。支持三种模式：

| 调用方式 | 行为 |
|----------|------|
| `/novel-scenes {id} 1-5` | 手动指定范围，处理单批 |
| `/novel-scenes {id}` | 默认处理前 5 章 |
| `/novel-scenes {id} all` | **自动循环**处理全书（默认每批 5 章） |
| `/novel-scenes {id} all:10` | 自动循环，自定义批次大小 |

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/tags.yaml` 获取合法标签值
3. 如存在 `outline.yaml` 和 `characters.yaml`，读取备用

## Schema

输出遵循 `docs/schemas/scene.schema.yaml`。

## 执行步骤

### 1. 扫描章节结构

读取 `source.txt`，**仅扫描章节标题行**（不读正文），建立章节索引：

```yaml
chapters:
  - {num: 1, title: "第1章 xxx", start_line: 1, end_line: 280}
  - {num: 2, title: "第2章 xxx", start_line: 281, end_line: 530}
  ...
total: 1070
avg_chars_per_chapter: ~3200
```

此索引用于：定位每批的读取范围、估算批次大小、最终覆盖检查。

### 2. 确定批次计划

| 模式 | 批次计划 |
|------|----------|
| 手动范围 `1-5` | 单批，按指定范围 |
| `all` | 自动计算：总章数 ÷ 批次大小，向上取整 |
| `all:N` | 同上，批次大小为 N |

**动态批次大小**（仅 `all` 模式未指定批次大小时）：
- 平均章节 ≤ 3000 字 → 每批 8 章
- 平均章节 3000-6000 字 → 每批 5 章（默认）
- 平均章节 > 6000 字 → 每批 3 章

### 3. 逐批执行（核心循环）

对每一批：

#### 3a. 读取本批原文

**只读当前批次的章节文本**（按章节索引的 start_line ~ end_line 定位），不读其他章节。

参考信息精简传递：
- `outline.yaml` → 仅传与本批章节相关的段落摘要
- `characters.yaml` → 仅传人物名册（名字+身份），不传完整弧线

#### 3b. 逐章拆分场景

对每一章：
- 按场景转换点（地点变化、时间跳转、视角切换、情节断裂）拆分
- 每个场景约 500-2000 字原文对应
- 场景 ID 格式：`ch{章号}_s{序号}`，如 `ch01_s02`

#### 3c. 为每个场景打多维标签

参照 `docs/schemas/scene.schema.yaml`，为每个场景填写 6 层标签：

**A. 内容层**：scene_type, conflict, stakes
**B. 人物层**：characters, relationship, interaction, power_dynamic, character_moment, moral_spectrum
**C. 情感层**：emotion, tension (1-5), reader_effect
**D. 结构层**：plot_stage, plot_function, pacing
**E. 技法层**：technique, dialogue_type, pov, info_delivery
**F. 物理层**：setting, scale, time_weather

**所有标签值必须从 `data/tags.yaml` 中选取。**

#### 3d. 标记精彩段落

特别出色的段落在 `highlights` 中标注行号范围和参考价值。

#### 3e. 立即写入文件

每个场景**生成后立即写入**独立文件：`data/novels/{material_id}/scenes/{scene_id}.yaml`

不要等一批全部完成再统一写入——这样即使中途中断，已处理的场景不会丢失。

#### 3f. 更新进度

每批完成后更新 `meta.yaml`：

```yaml
pipeline:
  current_stage: scenes
  scenes_processed: [1-5, 6-10]  # 追加本批范围
  scenes_total_chapters: 1070
```

#### 3g. 输出本批摘要

```
[批次 2/214] 第 6-10 章完成，本批 15 个场景
```

#### 3h. 进入下一批

- `all` 模式：**不等待确认**，直接进入下一批
- 手动模式：结束，提示后续命令

### 4. 全书覆盖检查（all 模式完成后）

全部批次执行完毕后，执行覆盖检查：

1. 扫描 `scenes/` 目录，提取所有场景文件的章节号
2. 对比步骤 1 的章节索引，找出缺失章节
3. 输出覆盖报告：

```
📊 覆盖检查
  总章节：1070
  已覆盖：1068 章
  缺失：第 233 章、第 891 章
  场景总数：3842 个
```

4. 如有缺失，**自动补处理**缺失章节（无需用户干预）
5. 补处理完成后再次检查，直到覆盖率 100%

### 5. 更新状态

全书覆盖检查通过后，将 `meta.yaml` 中 `status` 更新为 `complete`。
单批模式不改为 `complete`，保持 `tagged`。

## 上下文控制策略

防止 context window 爆炸的关键约束：

1. **只读当前批次原文** — 按章节索引定位，不加载其他章节
2. **参考信息最小化** — outline 只传本批相关段落，characters 只传名册
3. **即时写入** — 每个场景生成后立即写文件，不在内存中累积
4. **批间无累积** — 上一批的场景输出不带入下一批的上下文；唯一跨批传递的是进度状态（`scenes_processed`）
5. **动态批次大小** — 长章节自动缩小批次，避免单批过大

## 输出格式

### 单批模式

```
✅ 场景拆分完成

📚 素材：{name}
📖 处理范围：第{start}-{end}章
🎬 场景数：{N}个
📁 文件：data/novels/{id}/scenes/

本批场景概览：
  ch01_s01: {title} ({scene_type})
  ch01_s02: {title} ({scene_type})
  ...

后续：/novel-scenes {id} {next_range}  # 继续下一批
```

### all 模式

```
✅ 全书场景拆分完成

📚 素材：{name}
📖 总章节：{total}章（{batch_count}批完成）
🎬 场景总数：{N}个
📁 文件：data/novels/{id}/scenes/

📊 覆盖检查：{total}章全部覆盖 ✓

后续：
  /build-index {id}      # 构建索引
  /novel-pipeline continue {id}  # 继续后续流程
```

## 注意事项

- 场景粒度：一个场景 = 一个连续的戏剧单元（地点/时间/核心冲突不变）
- summary 控制在 50-100 字
- 标签值必须从字典选取，如需新值先 `/tag-add`
- 已存在的场景文件不覆盖，除非用户明确要求
- `all` 模式中断后可通过 `/novel-pipeline continue {id}` 恢复，从未处理的章节继续
