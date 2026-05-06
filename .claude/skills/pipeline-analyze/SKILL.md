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
python scripts/pipeline.py analyze <material_id>
```

## 执行顺序（已修复）

正确顺序：章级分析 → 大纲生成 → 世界观提取 → 人物提取 → 标签生成 → 同步数据库

章级分析先执行，确保骨架分析可使用全书章级摘要池而非原文片段。

### 各步骤说明

| 步骤 | 脚本 | 输入 | 输出 |
|------|------|------|------|
| 章级分析 | `chapter_analyze.py` | source.txt 按章切分 | `chapters.yaml`（支持断点续传） |
| 大纲生成 | `generate_outline.py` | 章级摘要池 | `outline/structure.yaml` 等 |
| 世界观提取 | `generate_worldbuilding.py` | 章级摘要池 | `worldbuilding/*.yaml` |
| 人物提取 | `generate_characters.py` | 章级摘要池 | `characters/profiles/*.yaml` |
| 标签生成 | `generate_tags.py` | source.txt + `data/tags.yaml` | 小说级标签 |
| 同步数据库 | `sync_db.py` | 所有 YAML + 向量 | PostgreSQL |

## 重试与断点续传

- **LLM 调用重试**：llm_client 使用 tenacity 指数退避，最多 8 次，自动处理 429/超时/5xx
- **断点续传**：每章分析完立即写入 `chapters/{n:04d}.yaml`，崩溃后重跑会从断点继续
- **章节截断**：按 token 数动态截断（配置项 `max_chapter_tokens`），而非硬截断字符

## 成功校验

1. `chapters.yaml` 存在且列表长度等于 `chapter_index.yaml` 的章节数
2. `outline/structure.yaml` 存在
3. `characters/profiles/` 下有人物小传文件
4. `meta.yaml` 中 `status: analyzed`
5. 终端输出 `分析流水线完成`

## 失败处理

| 症状 | 处理 |
|------|------|
| API 连接错误 | 自动重试，无需手动干预 |
| `chapters.yaml` 章节数少于 `chapter_index.yaml` | 重跑 `pipeline.py analyze`，会从断点继续 |
| 大纲结构不合理 | 可手动调整或重跑骨架分析 |