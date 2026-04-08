---
name: pipeline-analyze
description: 分析流水线：大纲 → 世界观 → 人物 → 标签
when_to_use: 素材已入库（status=raw 且 formatted=true），需要生成骨架分析
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

对已清洗的素材生成结构化分析产出物：大纲、世界观、人物体系、小说级标签。

**串联 4 个子 skill：`novel-outline` → `novel-worldbuilding` → `novel-characters` → `novel-tags`。**

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`
2. 确认 `source.txt` 存在且 `formatted: true`
3. 检查已有产出物——如部分文件已存在（如 `outline.yaml`），从缺失的阶段开始

## 恢复逻辑

| 已有文件 | 从哪里开始 |
|----------|-----------|
| 无 outline.yaml | outline |
| 有 outline，无 worldbuilding | worldbuilding |
| 有 outline + worldbuilding，无 characters | characters |
| 有 outline + worldbuilding + characters，无 tags | tags |
| 全部存在 | 输出"已完成"，不重复执行 |

## 执行步骤

### 1. 预览

```
📋 分析流程预览

素材：{name} ({material_id})
状态：{status}

将执行：
  1. novel-outline       → 生成大纲（结构+节奏+伏笔）
  2. novel-worldbuilding → 提取世界观设定
  3. novel-characters    → 生成人物体系
  4. novel-tags          → 生成小说级标签

{如有跳过} ⏭️ 已完成阶段将跳过：{列表}

确认开始？(yes/no)
```

### 2. 执行子 skill（确认后自动连续）

依次读取并执行每个子 skill 的 SKILL.md，**不再逐阶段确认**：

1. **novel-outline** → 产出 `outline.yaml`，status → `outlined`
2. **novel-worldbuilding** → 产出 `worldbuilding.yaml`
3. **novel-characters** → 产出 `characters.yaml`
4. **novel-tags** → 产出 `tags.yaml`，status → `tagged`

每步完成后输出简要进度：

```
[1/4] novel-outline ✅ 大纲已生成（{N}幕，{M}伏笔）
[2/4] novel-worldbuilding ✅ 世界观已提取
[3/4] novel-characters ✅ 人物体系已生成（{N}人）
[4/4] novel-tags ✅ 标签已生成
```

如某步失败，停止并报告，不继续后续阶段。

### 3. 更新 pipeline 状态

```yaml
pipeline:
  stages_completed: [material-add, source-format, outline, worldbuilding, characters, tags]
  outlined_at: {today}
  worldbuilding_at: {today}
  characters_at: {today}
  tags_at: {today}
```

### 4. 输出报告

```
✅ 分析流程完成

📚 素材：{name}
📖 大纲：{N}幕结构
🗺️ 世界观：{power_system} + {geography_count}地点 + {factions_count}势力
👥 人物：{character_count}人（{protagonist_count}主角）
🏷️ 标签：{genre} / {tone}

后续操作：
  /pipeline-scenes {material_id}      # 拆分全书场景
  /novel-pipeline full {material_id}  # 继续完整流程
```

## 硬约束

- MUST 先预览再执行（仅确认一次）
- MUST 用户确认后自动连续执行 4 个阶段，不再逐阶段确认
- MUST 支持从中断点恢复（检查已有文件）
- MUST 记录 pipeline 状态
- NEVER 在 worldbuilding/characters 之前跳过 outline（outline 提供导航信息）

## References

- [novel-outline/SKILL.md](../novel-outline/SKILL.md)
- [novel-worldbuilding/SKILL.md](../novel-worldbuilding/SKILL.md)
- [novel-characters/SKILL.md](../novel-characters/SKILL.md)
- [novel-tags/SKILL.md](../novel-tags/SKILL.md)
- [AGENTS.md](../../../AGENTS.md)
