---
name: tag-merge
description: 将同义或重复标签值批量合并为统一值，并同步更新事件文件、索引、清单与 SQLite；这是需要先评估影响并确认的批量改写操作
---

# 任务

把一个旧标签值合并到新标签值，并同步更新所有引用。

## 边界

用于：
- 发现同义值
- 发现重复值
- 需要统一标签体系

不用于：
- 新增标签值

## 输入

- 维度
- 旧值
- 新值

## 默认执行路径

### 1. 影响评估

先统计：

- 多少事件文件会受影响
- 多少小说标签会受影响
- 哪些 `events_index.yaml` / `events_manifest.yaml` 需要更新
- SQLite 是否需要局部重建或全量重建

### 2. 用户确认

这是批量改写操作，必须在影响评估后等待确认。

### 3. 执行合并

确认后按顺序：

1. 更新 `data/tags.yaml`
2. 替换事件文件与小说级标签
3. 更新 manifest / index
4. 重建 SQLite

### 4. 验证一致性

验证：

- 旧值已不再出现
- 新值引用完整
- YAML / 索引 / SQLite 三层一致

## 输出要求

至少输出：

- 合并维度与映射关系
- 影响文件数量
- 是否已重建索引和 SQLite

## 关键硬约束

- 必须先评估影响，再确认
- 不能只改字典不改引用
- 必须更新 YAML、manifest、index、SQLite 四层

## 仅在需要时读取

- `references/impact-checklist.md`
- `../_shared/references/skill-conventions.md`
- `../../../AGENTS.md`
