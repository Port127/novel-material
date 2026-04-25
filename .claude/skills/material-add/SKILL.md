---
name: material-add
description: 将新素材添加到共享素材库，生成唯一 material_id、目录结构和基础 meta.yaml
---

# 任务

把原始素材注册进库，创建最小可用目录结构。

## 边界

用于：
- 新素材首次入库
- 仅注册原文，不做分析

不用于：
- 直接导入已分析文件夹（交给 `material-import`）
- 跳过去重检查

## 输入

- 文件路径
- 可选类型参数

## 默认执行路径

### 1. 基础检查

- 文件存在
- 能判断素材类型

### 2. 去重检查

读取 `data/index.yaml` 做两类检查：

- 书名相似
- 文件路径重复

去重默认是**提醒，不是阻断**。  
只有发现明显冲突时，才在最终回复里要求用户确认是否作为新版本继续入库。

### 3. 生成 ID

格式必须是：

`nm_{type}_{YYYYMMDD}_{random4}`

生成后仍需检查是否撞 ID。

### 4. 建目录并写基础文件

最少创建：

- `data/novels/{material_id}/`
- `meta.yaml`
- `source.txt`
- `events/`

### 5. 更新全局索引

把素材路由信息写入 `data/index.yaml`。

## 输出要求

至少输出：

- `material_id`
- 名称
- 目标目录
- 当前状态 `raw`
- 下一步建议

## 关键硬约束

- 必须生成新 ID
- 去重只提醒，不擅自阻断
- 不把已分析素材误当作 raw 导入

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `../../../docs/schemas/meta.schema.yaml`
- `../../../AGENTS.md`
