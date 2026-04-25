---
name: novel-tags
description: 为整部小说生成宏观标签，包括类型、基调、叙事结构、风格、长板和套路识别
---

# 任务

生成小说级标签文件 `tags.yaml`。

## 边界

用于：
- 描述整本小说的宏观特征

不用于：
- 替代事件级标签
- 被少数章节风格误导

## 输入

- `material_id`

## 默认执行路径

### 1. 优先利用已有产出

优先读取：

- `outline/`
- `worldbuilding/`
- `characters/`

只在必要时抽样少量原文验证风格判断。

### 2. 逐维度判断

重点维度：

- `genre`
- `tone`
- `narrative`
- `style`
- `tropes`
- `good_for`

### 3. 合法值约束

凡是字典型字段，必须从 `data/tags.yaml` 的小说级维度选取。

### 4. 质量检查

重点检查：

- 合法值
- `good_for` 非空且具体
- `theme` 非空

### 5. 状态写回

完成后推进到 `tagged`。

## 输出要求

至少输出：

- 类型
- 基调
- 叙事结构
- prose / strength
- tropes
- 第一条 `good_for`

## 关键硬约束

- 优先用已有产出，少量抽样原文
- 宏观判断，不被局部偏差带偏
- 需要新值时先走 `tag-add`

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/dimensions.md`
- `../../../docs/schemas/novel-tags.schema.yaml`
- `../../../data/tags.yaml`
- `../../../AGENTS.md`
