---
name: material-add
description: 将新小说添加到共享素材库。当用户提供 .txt 小说文件路径并要求入库时使用。处理入库、章节切分、LLM 分析、数据库同步等完整流程。
---

# material-add

将新小说添加到共享素材库。

## 前置条件

- 用户提供一个 `.txt` 格式的小说文件路径
- 支持自动编码检测（UTF-8/GBK/Big5/Latin-1）
- 支持中文数字章节标题（如"第一章"，预处理层自动转换为"第1章")

## 执行命令

```bash
nm pipeline full <小说文件路径>
```

> 该命令会串联执行：入库 → 章级分析(LLM) → 向量化 → 骨架分析(LLM) → 精调 → 同步数据库。
> 章级分析阶段会对每章调用一次 LLM API，但有断点续传机制，崩溃后可从断点继续。

## 产物

```
data/novels/{material_id}/
├── meta.yaml               # 小说元信息（name/author/status/...）
├── source.txt              # 清洗后原文
├── chapter_index.yaml      # 章节索引（章号/标题/行号/字数）
├── chapters.yaml           # 章级分析结果（摘要/人物/标签/张力）
├── chapter_embeddings.npz  # 章节向量（用于语义检索）
├── outline/                # 大纲（structure.yaml / sequences.yaml / beats.yaml）
├── characters/             # 人物（_index.yaml + profiles/*.yaml）
└── worldbuilding/          # 世界观（factions/regions/power_systems）
```

## 成功校验

运行完成后，逐项检查：

1. `data/novels/{material_id}/chapter_index.yaml` 是否存在且章节数 > 0
2. `data/novels/{material_id}/chapters.yaml` 是否存在且非空列表
3. `data/novels/{material_id}/meta.yaml` 中 `status` 字段是否为 `indexed`
4. 终端输出是否包含 `流水线完成`

## 失败处理

| 症状 | 原因 | 处理 |
|------|------|------|
| "未检测到章节名" | 章节格式不标准 | 检查文件是否使用非标准章节标题格式 |
| API 连接错误 | 网络问题 | llm_client 自动重试，无需手动干预 |
| 中途崩溃 | API 限流等 | 重跑分析命令，会从断点继续 |