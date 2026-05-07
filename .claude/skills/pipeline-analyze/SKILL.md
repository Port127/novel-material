---
name: pipeline-analyze
description: 对已入库小说执行 LLM 结构化分析。当素材状态为 clean 且需要章级分析、大纲生成、人物提取、世界观提取时使用。每章调用一次 API，支持断点续传和自动重试。
---

# pipeline-analyze

分析流水线：对已入库的小说进行 LLM 结构化分析。

## 前置条件

- 素材必须已完成入库（`meta.yaml` 中 `status: clean`）
- `chapter_index.yaml` 存在且非空
- `source.txt` 存在
- `.env` 中已配置有效的 `LLM_API_KEY`
- NEVER 对 `status` 已为 `analyzed` 的素材重复执行（会覆盖已有数据）

## 执行命令

```bash
nm pipeline outline <material_id>
nm pipeline worldbuilding <material_id>
nm pipeline characters <material_id>
nm pipeline tags <material_id>
```

## 执行顺序

正确顺序：大纲生成 → 世界观提取 → 人物提取 → 标签生成 → 精调 → 同步数据库

### 各步骤说明

| 步骤 | 命令 | 输入 | 输出 |
|------|------|------|------|
| 大纲生成 | `nm pipeline outline` | 章级摘要池 | `outline/structure.yaml` 等 |
| 世界观提取 | `nm pipeline worldbuilding` | 章级摘要池 | `worldbuilding/*.yaml` |
| 人物提取 | `nm pipeline characters` | 章级摘要池 | `characters/profiles/*.yaml` |
| 标签生成 | `nm pipeline tags` | source.txt + 标签字典 | 小说级标签 |
| 精调 | `nm pipeline refine` | 所有 YAML | 更新统计数据 |

## 成功校验

1. `chapters.yaml` 存在且列表长度等于 `chapter_index.yaml` 的章节数
2. `outline/structure.yaml` 存在
3. `characters/profiles/` 下有人物小传文件
4. `meta.yaml` 中 `status: analyzed`

## 失败处理

| 症状 | 处理 |
|------|------|
| API 连接错误 | 自动重试，无需手动干预 |
| 大纲结构不合理 | 可手动调整或重跑骨架分析 |