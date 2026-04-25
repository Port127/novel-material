---
name: material-import
description: 导入外部已按本库 schema 分析好的素材目录，重新生成 material_id 并注册到素材库；用于导入已分析产物，不用于只入库原文
---

# 任务

把外部已分析好的素材目录导入当前库，保持原始来源不动。

## 边界

用于：
- 外部目录已经有 outline / characters / events / tags 等产物
- 不想重新跑完整 pipeline

不用于：
- 仅导入原文
- 复用外部 `material_id`

## 输入

- 外部文件夹路径
- 可选书名 / 作者覆盖参数

## 默认执行路径

### 1. 扫描目录

识别是否存在：

- `source.txt`
- `outline/` 或旧版 outline 文件
- `worldbuilding/`
- `characters/`
- `tags.yaml`
- `events/`
- `events_index.yaml`
- `events_manifest.yaml`
- `stats.*`

如果没有任何有效分析产物，直接失败。

### 2. 提取元信息

优先级：

1. 显式参数
2. 外部 `meta.yaml`
3. 各分析文件中的标题 / 作者字段
4. 文件夹名

### 3. 校验

至少检查：

- YAML 可解析
- 标签值合法
- 事件文件满足基本 schema

非法标签不能直接吞掉，必须在结果里明确说明处理方式。

### 4. 推断状态

根据已存在产物推断导入后的状态：

- `raw`
- `outlined`
- `tagged`
- `complete`
- `refined`

### 5. 去重与确认边界

导入默认直接执行；只有以下情况才停下来确认：

- 疑似与现有素材重复
- 发现大量非法标签，需要决定是忽略还是扩字典

### 6. 执行导入

必须：

1. 重新生成 `material_id`
2. 复制文件到 `data/novels/{material_id}/`
3. 写入新的 `meta.yaml`
4. 更新 `data/index.yaml`
5. 如有 events 但缺索引，自动调用 `build-index`

## 输出要求

至少输出：

- 新 `material_id`
- 推断出的 status
- 导入了哪些文件
- 哪些文件被跳过，为什么
- 是否自动补建索引

## 关键硬约束

- 永远重新生成 `material_id`
- 永远复制，不移动原目录
- 非法标签必须显式处理
- 有 events 缺索引时必须补建

## 仅在需要时读取

- `references/import-validation.md`
- `../_shared/references/skill-conventions.md`
- `../build-index/SKILL.md`
- `../../../docs/schemas/meta.schema.yaml`
- `../../../docs/schemas/event-unit.schema.yaml`
- `../../../docs/schemas/outline.schema.yaml`
- `../../../docs/schemas/worldbuilding.schema.yaml`
- `../../../docs/schemas/characters.schema.yaml`
- `../../../docs/schemas/novel-tags.schema.yaml`
- `../../../AGENTS.md`
