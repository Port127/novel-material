---
name: pipeline-ingest
description: 入库流水线，处理格式清洗和章节切分。不涉及 LLM 调用。当用户需要将原始 .txt 小说文件入库时使用，是分析阶段的前置步骤。
---

# pipeline-ingest

入库 + 格式清洗 + 章节切分。这是 Pipeline 的第一个阶段，不涉及任何 LLM 调用。

## 执行命令

```bash
python scripts/pipeline.py ingest <小说文件路径>
```

或直接调用底层脚本：

```bash
python scripts/core/ingest.py <小说文件路径>
```

## 前置条件

- 输入文件为小说文本文件（自动检测编码：UTF-8/GBK/Big5/Latin-1）
- 支持的章节格式：
  - 阿拉伯数字：第1章、第1节、第1回、第1篇
  - 中文数字：第一章、第一百二十三章等（预处理层自动转换）
  - 特殊章节：楔子、引子、序章、终章、尾声
  - 数字+顿号：1、标题（如"1、五千双皮鞋")

## 处理流程

1. 自动检测文件编码并转换为 UTF-8
2. 去广告水印（网站提示、求票、二维码等）
3. 中文数字章节标题转换为阿拉伯数字
4. 空白归一化（全角空格、连续空行）
5. 正则检测章节标题行号
6. 按章节切分内容
7. 保存 `source.txt`（清洗后原文）
8. 生成 `chapter_index.yaml`（章号/标题/起止行号/字数）
9. 生成 `meta.yaml`（name 取自文件名，status 为 clean）
10. 创建空目录结构
11. 更新 `data/index.yaml` 全局索引

## 产物

```
data/novels/{material_id}/
├── meta.yaml               # status: clean
├── source.txt              # 清洗后原文
├── chapter_index.yaml      # 章节索引
├── chapters.yaml           # 空列表（待章级分析填充）
├── chapters/               # 空目录（章级分析逐章写入）
├── outline/                # 空目录
├── characters/profiles/    # 空目录
└── worldbuilding/          # 空目录
```

## 成功校验

1. 终端输出 `识别到 N 个章节`，N > 0
2. `chapter_index.yaml` 存在且列表非空
3. `meta.yaml` 中 `status: clean`
4. 终端输出 `入库完成` 和 `material_id`