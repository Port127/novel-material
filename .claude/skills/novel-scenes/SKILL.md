---
name: novel-scenes
description: 将小说按场景拆分，为每个场景打多维标签（支持分批执行）
when_to_use: 用户想要拆分小说场景并打标签
argument-hint: "[material_id] [章节范围，如 1-5]"
arguments: material_id, chapter_range
---

# 任务

将小说按场景拆分，为每个场景生成多维标签。**支持分批执行**，每次处理指定章节范围。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/novels/{material_id}/source.txt`
3. 读取 `data/tags.yaml` 获取合法标签值
4. 如存在 `outline.yaml` 和 `characters.yaml`，优先参考

## Schema

输出遵循 `docs/schemas/scene.schema.yaml`。

## 执行步骤

### 1. 定位章节范围

根据参数中的章节范围（如 `1-5`），在 source.txt 中定位对应文本。

如未指定范围，默认处理前 5 章。**严禁一次处理全书**。

### 2. 逐章拆分场景

对每一章：
- 按场景转换点（地点变化、时间跳转、视角切换、情节断裂）拆分
- 每个场景约 500-2000 字原文对应
- 场景 ID 格式：`ch{章号}_s{序号}`，如 `ch01_s02`

### 3. 为每个场景打多维标签

参照 `docs/schemas/scene.schema.yaml`，为每个场景填写 6 层标签：

**A. 内容层**：scene_type, conflict, stakes
**B. 人物层**：characters, relationship, interaction, power_dynamic, character_moment, moral_spectrum
**C. 情感层**：emotion, tension (1-5), reader_effect
**D. 结构层**：plot_stage, plot_function, pacing
**E. 技法层**：technique, dialogue_type, pov, info_delivery
**F. 物理层**：setting, scale, time_weather

**所有标签值必须从 `data/tags.yaml` 中选取。**

### 4. 标记精彩段落

特别出色的段落在 `highlights` 中标注行号范围和参考价值。

### 5. 写入场景文件

每个场景写入独立文件：`data/novels/{material_id}/scenes/{scene_id}.yaml`

### 6. 更新状态

处理完所有章节后，将 `meta.yaml` 中 `status` 更新为 `tagged`。
全书处理完毕后更新为 `complete`。

## 输出格式

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

## 注意事项

- **每次最多处理 5 章**，避免 token 耗尽
- 场景粒度：一个场景 = 一个连续的戏剧单元（地点/时间/核心冲突不变）
- summary 控制在 50-100 字
- 标签值必须从字典选取，如需新值先 `/tag-add`
- 已存在的场景文件不覆盖，除非用户明确要求
