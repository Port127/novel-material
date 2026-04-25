---
name: novel-worldbuilding
description: 从原文中提取世界观设定，输出到文件夹结构，包括力量体系、地理、势力与 lore
---

# 任务

提取世界观设定，生成 `worldbuilding/` 文件夹。

## 边界

用于：
- 建立力量体系、地理、势力和背景知识

不用于：
- 替代人物体系
- 在本阶段穷尽所有交叉引用

## 输入

- `material_id`

## 默认执行路径

### 1. 前置检查

- `source.txt` 存在
- 有 `outline/` 时优先用其做导航

### 2. 读取策略

优先采用：

- outline 导航
- 定向采样
- 必要时补扫

### 3. 提取四类信息

- 力量体系
- 地理空间
- 势力组织
- lore（历史 / 物品 / 物种 / 术语）

### 4. 粒度自适应

- 地理 ≤ 3：单文件
- 地理 > 3：文件夹
- 势力 ≤ 3：单文件
- 势力 > 3：文件夹

### 5. 初步交叉引用

可写初步 `key_events` 或关联关系，但完整交叉引用留给 `refine`。

### 6. 状态写回

完成后推进到世界观阶段状态。

## 输出要求

至少输出：

- 是否有力量体系
- 地理数量及粒度形式
- 势力数量及粒度形式
- lore 统计

## 关键硬约束

- 不一次性读全文
- 粒度随数量变化
- `_index.yaml` 只放概览和统计

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/granularity.md`
- `../../../docs/schemas/worldbuilding.schema.yaml`
- `../../../AGENTS.md`
