---
name: material-import
description: 导入外部已分析好的素材目录，跳过 LLM 分析直接入库。用于从其他 novel-material 实例迁移数据、导入人工标注素材或恢复备份。
---

# material-import

导入外部已分析好的素材目录（跳过 LLM 分析，直接入库）。

## 前置条件

- 外部目录结构必须符合 `data/schemas/` 中定义的 Schema 规范
- 至少包含 `meta.yaml` 和 `chapter_index.yaml`
- 标签值必须来自 PostgreSQL 数据库中的 tags 表

## 执行命令

```bash
nm material import <素材目录路径>
```

## 流程

1. 读取外部素材目录
2. 生成新的 `material_id`（`nm_novel_YYYYMMDD_xxxx`）
3. 校验标签合法性（使用数据库验证）
4. 复制到 `data/novels/{new_material_id}/`
5. 更新 `data/index.yaml`
6. 同步到 PostgreSQL

## 成功校验

1. `data/novels/{new_material_id}/` 目录存在且结构完整
2. `data/index.yaml` 中包含新条目
3. 终端输出新生成的 `material_id`

## 与 material-add 的区别

| | material-add | material-import |
|---|---|---|
| 输入 | 原始 .txt 文件 | 已分析好的素材目录 |
| LLM 调用 | 需要（章级分析 + 骨架分析） | 不需要 |
| 耗时 | 长（依赖 API） | 短（纯文件操作） |