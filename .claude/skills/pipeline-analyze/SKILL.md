---
name: pipeline-analyze
description: 对已清洗素材生成骨架分析；串联 novel-outline、novel-worldbuilding、novel-characters、novel-tags
---

# 任务

对已清洗素材生成结构化分析产物：

- `outline/`
- `worldbuilding/`
- `characters/`
- `tags.yaml`

## 适用边界

用于：
- `formatted=true` 后进入骨架分析
- 从 outline/worldbuilding/characters/tags 的中断点恢复

不用于：
- 直接替代子 skill
- 跳过 outline 直接做下游

## 输入

- `material_id`

## 默认执行路径

### 1. 前置检查

- `meta.yaml` 存在
- `source.txt` 存在
- `formatted = true`

### 2. 恢复判断

按已有产物判断起点：

| 已有文件 | 从哪里开始 |
|----------|-----------|
| 无 `outline/_index.yaml` | `novel-outline` |
| 只有 outline | `novel-worldbuilding` |
| 有 outline + worldbuilding | `novel-characters` |
| 有 outline + worldbuilding + characters | `novel-tags` |
| 全部都有 | 输出“已完成” |

### 3. 执行顺序

按固定顺序推进：

1. `novel-outline`
2. `novel-worldbuilding`
3. `novel-characters`
4. `novel-tags`

每一步都要等本步验证通过，再继续下一步。

### 4. 质量检查

执行完成后依次运行：

```bash
python scripts/core/validate_yaml.py outline {material_id}
python scripts/core/validate_yaml.py worldbuilding {material_id}
python scripts/core/validate_yaml.py characters {material_id}
python scripts/core/validate_yaml.py novel-tags {material_id}
```

并额外检查：

- `characters/_index.yaml` 中主角和反派不应为空
- `outline/_index.yaml` 的 `structure_summary.acts >= 2`

### 5. 状态写回

在 `meta.yaml` 中写入：

- `outlined_at`
- `worldbuilding_at`
- `characters_at`
- `tags_at`
- `stages_completed` 更新为分析阶段完成

## 输出要求

至少输出：

- 从哪一步开始恢复
- 四个子产物是否完成
- 关键规模摘要（幕数、人物数、地点/势力数、标签概览）
- 下一步建议：`pipeline-events`

## 关键硬约束

- 不跳过 outline
- 不逐阶段反复确认
- 子 skill 失败即停止，不继续后续步骤

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `../novel-outline/SKILL.md`
- `../novel-worldbuilding/SKILL.md`
- `../novel-characters/SKILL.md`
- `../novel-tags/SKILL.md`
- `../../../AGENTS.md`
