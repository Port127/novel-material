---
name: refine
description: 基于证据的精调工具，根据章级分析数据调整大纲/人物/标签的统计信息。当章级分析完成后需要更新统计元数据时使用。
---

# refine

基于证据的精调工具。读取章级分析数据，**调整**（而非增量追加）大纲/人物/标签中的统计信息。

## 核心原则

1. **基于证据**：所有调整必须来自 `chapters.yaml` 中的实际数据，不凭空生成
2. **调整而非增量**：可以删除、合并、修正，不无限膨胀
3. **幂等性**：多次运行同一素材，结果应该一致

## 前置条件

- `chapters.yaml` 存在且非空列表
- 对应的 `outline/_index.yaml`、`characters/_index.yaml` 存在（不存在的模块会被自动跳过）
- NEVER 对 `chapters.yaml` 为空的素材执行（打印错误后退出）

## 执行命令

```bash
python scripts/utils/refine.py <material_id>
```

> 通常不需要直接调用。`pipeline.py finalize` 会自动调用此脚本。

## 精调内容

### 大纲精调（`refine_outline`）
- 统计 `章末悬念` 标签出现次数 → 写入 `outline/_index.yaml` 的 `hook_count`
- 计算所有章节的平均张力值 → 写入 `avg_tension`
- 写入 `refined_at` 时间戳

### 人物精调（`refine_characters`）
- 遍历 `chapters.yaml` 中的 `characters_appear` 字段
- 统计每个人物的总出场次数 → 更新 `profiles/*.yaml` 的 `appearance_count`
- 计算首次/末次出场章节 → 更新 `first_appearance_chapter` / `last_appearance_chapter`
- 写入 `refined_at` 时间戳

### 标签精调（`refine_tags`）
- 统计 `chapter_function` 字段的频率分布
- 取 Top 5 最常见的章节功能标签 → 写入 `tags.yaml` 的 `top_chapter_functions`
- 写入 `refined_at` 时间戳

## 成功校验

终端输出格式：
```
精调完成
  outline: 已精调
  characters: 已精调
  tags: 已精调
```

如果某模块的前置文件不存在，会显示 `跳过` 而非报错。