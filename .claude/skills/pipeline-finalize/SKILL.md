---
name: pipeline-finalize
description: 收尾流水线，基于章级分析数据进行精调后同步到数据库。当素材状态为 analyzed 且需要统计精调和数据库同步时使用。
---

# pipeline-finalize

收尾流水线：基于章级分析数据进行精调，然后同步到数据库。

## 前置条件

- 素材必须已完成分析（`meta.yaml` 中 `status: analyzed`）
- `chapters.yaml` 存在且非空列表（精调需要章级数据作为证据）
- NEVER 对 `chapters.yaml` 为空的素材执行精调（无数据支撑，结果无意义）

## 执行命令

```bash
nm pipeline refine <material_id>
```

## 流程

1. **精调（refine）**：基于 `chapters.yaml` 中的章级数据，自动调整：
   - 大纲：统计钩子数量（`章末悬念` 标签出现次数）、计算平均张力值
   - 人物：更新出场次数、首次/末次出场章节
   - 标签：统计最常见的章节功能标签分布
2. **同步数据库（sync）**：将所有 YAML 数据和向量写入 PostgreSQL

## 成功校验

1. 终端输出 `精调完成`
2. `outline/_index.yaml` 中 `refined_at` 字段已更新
3. `characters/_index.yaml` 中 `refined_at` 字段已更新
4. 数据库 `novels` 表中能查询到该 `material_id`