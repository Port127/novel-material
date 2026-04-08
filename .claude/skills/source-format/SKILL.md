---
name: source-format
description: 清洗格式化入库原文（繁简转换、广告清理、章节标准化、缺章检测）
when_to_use: 素材入库后、大纲生成前，需要清洗原文质量
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

对已入库的小说原文 `source.txt` 进行格式清洗，输出清洗后的文本和格式报告。

**优先使用固化脚本** `scripts/core/source_format.py`，仅在脚本不满足需求时动态补充。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在且 status 为 `raw`
2. 确认 `data/novels/{material_id}/source.txt` 存在

## 执行步骤

### 1. 备份原始文件

将 `source.txt` 复制为 `source.raw.txt`（仅首次执行）。

### 2. 运行固化脚本

```bash
python scripts/core/source_format.py \
  data/novels/{material_id}/source.txt \
  data/novels/{material_id}/source.txt \
  data/novels/{material_id}/format_report.yaml
```

脚本覆盖的清洗操作：

| 功能 | 实现方式 |
|------|----------|
| 章节结构分析（缺章/重复/短章） | 正则匹配 + 连续性检测 |
| 章节名标准化（中文数字→阿拉伯、格式统一） | 中文数字转换 + 正则替换 |
| 繁简转换 | `opencc` 库（需安装） |
| 引号修复（双重引号、直引号→弯引号） | 字符串替换 + 奇偶配对 |
| 广告/乱码清理 | 预置正则模式列表 |
| 标点统一（省略号、破折号） | 正则替换 |
| 空白格式标准化（多空行、行首空白） | 逐行处理 |

首次运行前安装依赖：`pip install -r scripts/requirements.txt`

### 3. 检查脚本输出

读取脚本的 stdout 摘要和生成的 `format_report.yaml`，检查：

- **opencc 是否可用**：如 stdout 含 `WARNING: opencc 未安装`，提示用户安装
- **SUSPICIOUS 项**：逐条检查是否需要人工确认
- **异常情况**：脚本未覆盖的特殊格式问题

### 4. 动态补充处理（仅在需要时）

如果脚本输出中发现以下情况，**才**动态生成补充脚本：

| 场景 | 处理方式 |
|------|----------|
| 原文使用非标准章节格式（如自定义分卷、番外） | 动态生成针对性正则 |
| 特殊引号风格（如日式「」混用） | 动态调整引号规则 |
| 脚本未识别的广告模式 | 追加广告正则并重跑 |
| 编码异常（非 UTF-8 源文件） | 动态检测编码并转换 |

动态生成的补充脚本应写入 `scripts/generated/`（如 `scripts/generated/format_{小说简称}.py`），与预制脚本隔离。

**如果脚本输出正常、无异常，跳过此步骤。**

### 5. 生成章节索引 (chapter_index.yaml)

格式清洗完成后，扫描清洗后的 `source.txt`，生成持久化章节索引文件 `chapter_index.yaml`：

```yaml
# data/novels/{material_id}/chapter_index.yaml
total: 1070
chapters:
  - num: 1
    title: "第1章 喝酒不开车"
    start_line: 1
    end_line: 280
  - num: 2
    title: "第2章 重生回到2002年"
    start_line: 281
    end_line: 530
  # ...
```

此文件是**下游 skill 的关键依赖**：
- `novel-scenes` 的 `chapter` 字段必须从此文件逐字拷贝
- `validate_yaml.py` 用此文件校验章节名匹配
- `novel-outline` / `novel-scenes` 用此文件定位章节读取范围

如果 `format_report.yaml` 中已包含完整章节列表，可直接提取为 `chapter_index.yaml`。

### 6. 更新 meta.yaml

在 `meta.yaml` 中增加 `formatted: true`、`format_date` 和 `chapters` 字段。

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
📄 章节索引：data/novels/{id}/chapter_index.yaml
📄 原始备份：data/novels/{id}/source.raw.txt
```

## 注意事项

- 原始文件始终保留备份 `source.raw.txt`
- 不修改实际内容（剧情、对话等），只做格式层面清洗
- 遇到无法自动判断的问题标记为 suspicious，交由用户确认
- 固化脚本处理大文件无 token 限制，agent 只需读取脚本的输出摘要

## References

- [scripts/core/source_format.py](../../../scripts/core/source_format.py) — 固化清洗脚本
- [scripts/requirements.txt](../../../scripts/requirements.txt) — 脚本依赖
- [format-report.schema.yaml](../../../docs/schemas/format-report.schema.yaml)
- [AGENTS.md](../../AGENTS.md)
