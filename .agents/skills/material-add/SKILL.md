# material-add

将新小说添加到共享素材库。

## 前置条件

- 用户提供了一个 `.txt` 格式的小说文件路径
- 文件编码为 UTF-8
- ⚠️ 当前系统缺少文本预处理层（缺陷 C1）：中文数字章节标题（如"第一章"）无法被正则识别，会导致切分失败。待 `preprocess.py` 模块完成后此限制将消除

## 执行命令

```bash
python scripts/pipeline.py full <小说文件路径>
```

> 该命令会串联执行：入库 → 骨架分析(LLM) → 章级分析(LLM) → 同步数据库。
> ⚠️ **高危操作**：章级分析阶段会对每章调用一次 LLM API，耗时长且无断点续传。如中途崩溃，已消耗的 API 费用无法恢复。

## 产物

```
data/novels/{material_id}/
├── meta.yaml               # 小说元信息（name/author/status/...）
├── source.txt              # 清洗后原文
├── chapter_index.yaml      # 章节索引（章号/标题/行号/字数）
├── chapters.yaml           # 章级分析结果（摘要/人物/标签/张力）
├── outline/                # 大纲（structure.yaml / sequences.yaml / beats.yaml）
├── characters/             # 人物（_index.yaml + profiles/*.yaml）
└── worldbuilding/          # 世界观（factions/regions/power_systems）
```

## 成功校验

运行完成后，Agent 应逐项检查：

1. `data/novels/{material_id}/chapter_index.yaml` 是否存在且章节数 > 0
2. `data/novels/{material_id}/chapters.yaml` 是否存在且非空列表
3. `data/novels/{material_id}/meta.yaml` 中 `status` 字段是否为 `analyzed`
4. 终端输出是否包含 `完整流水线完成`

## 失败处理

| 症状 | 原因 | 处理 |
|------|------|------|
| "未检测到章节名" | 文件使用中文数字章节名 | 告知用户当前不支持，等待正则修复 |
| `NameError: material_dir` | 已知代码 Bug | 需先修复 `ingest.py` 第 123 行 |
| API 超时 / 429 错误 | LLM 限流 | 当前无自动重试，需手动重跑 `pipeline.py analyze` |
