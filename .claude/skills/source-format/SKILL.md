---
name: source-format
description: 清洗格式化入库原文（繁简转换、广告清理、章节标准化、缺章检测）
when_to_use: 素材入库后、大纲生成前，需要清洗原文质量
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

对已入库的小说原文 `source.txt` 进行格式清洗，输出清洗后的文本和格式报告。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在且 status 为 `raw`
2. 确认 `data/novels/{material_id}/source.txt` 存在

## 执行步骤

### 1. 备份原始文件

将 `source.txt` 复制为 `source.raw.txt`（仅首次执行）。

### 2. 章节结构分析

扫描全文，提取章节标题行：
- 识别章节标题模式（"第X章"/"第X回"/"Chapter X"/纯数字等）
- 统计总章节数
- 检测章节号连续性，标记缺失章节
- 检测重复章节（标题重复或内容高度相似）
- 检测空章/短章（字数 < 200 的异常章节）

### 3. 章节名标准化

统一章节标题格式为 `第{N}章 {章节名}`：
- "第一章" → "第1章"
- "Chapter 1" → "第1章"
- 去除多余空格、特殊字符
- 保留原始章节名（副标题部分不改）

### 4. 繁简转换

全文繁体中文 → 简体中文。保留人名、地名中的繁体用法除外（如有特殊需求由用户指定）。

### 5. 引号修复

- 检测不配对引号（单引号、双引号）
- 修复 `""` 双重引号 → `"`
- 统一引号风格为中文引号 `「」`/`""` （以原文主流风格为准）

### 6. 广告/乱码清理

移除常见干扰内容：
- 网站广告语（"本书来自xx网"、"更多好书请访问"等）
- 求票/求订阅语句
- 乱码字符（非 CJK/ASCII 的异常字节）
- 连续重复的分隔符行

### 7. 格式统一

- 段落间距标准化（空行统一为单空行）
- 去除行首/行尾多余空白
- 统一省略号为 `……`（6个点）
- 统一破折号为 `——`（2个）

### 8. 生成格式报告

输出 `format_report.yaml`，参照 `docs/schemas/format-report.schema.yaml`。

### 9. 覆写 source.txt

用清洗后的文本覆写 `source.txt`。

### 10. 更新 meta.yaml

在 `meta.yaml` 中增加 `formatted: true` 和 `format_date` 字段。

## 输出格式

```
✅ 源文件格式化完成

📚 素材：{name}
📊 格式报告：

  章节：{total_chapters} 章
  缺失：{missing} 章 {列表}
  重复：{duplicate} 章
  短章：{short} 章

  修复统计：
    繁简转换：{n} 处
    引号修复：{n} 处
    广告清除：{n} 处
    章节名标准化：{n} 处

  ⚠️ 需人工确认：
    - 第233章：章节缺失，从232直接跳到234
    - 第789章：字数仅120字，疑似截断

📄 报告文件：data/novels/{id}/format_report.yaml
📄 原始备份：data/novels/{id}/source.raw.txt
```

## 注意事项

- 原始文件始终保留备份 `source.raw.txt`
- 不修改实际内容（剧情、对话等），只做格式层面清洗
- 遇到无法自动判断的问题标记为 suspicious，交由用户确认
- 大文件分段处理，避免 token 溢出

## References

- [format-report.schema.yaml](../../../docs/schemas/format-report.schema.yaml)
- [AGENTS.md](../../AGENTS.md)
