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

## 当前执行顺序（存在已知缺陷）

> ⚠️ 当前代码的执行顺序为：大纲 → 世界观 → 人物 → 标签 → 章级分析 → 同步数据库。
> 这是**错误的**（缺陷 A1）：大纲生成在章级分析之前，只能读到前 5000 字，无法获得全书视角。
> 正确的顺序应为：章级分析 → 大纲/世界观/人物/标签。待代码修复后此文档将更新。

### 各步骤说明

| 步骤 | 脚本 | 输入 | 输出 |
|------|------|------|------|
| 大纲生成 | `generate_outline.py` | source.txt 前 5000 字 ⚠️ | `outline/structure.yaml` 等 |
| 世界观提取 | `generate_worldbuilding.py` | source.txt | `worldbuilding/*.yaml` |
| 人物提取 | `generate_characters.py` | source.txt | `characters/profiles/*.yaml` |
| 标签生成 | `generate_tags.py` | source.txt + `data/tags.yaml` | 小说级标签 |
| 章级分析 | `chapter_analyze.py` | source.txt 按章切分 | `chapters.yaml` |
| 同步数据库 | `sync_db.py` | 所有 YAML | PostgreSQL |

## LLM 调用风险

- 章级分析会对**每一章**调用一次 LLM API
- 当前无重试机制（缺陷 C4）：API 超时或 429 错误会导致整个脚本崩溃
- 当前无断点续传（缺陷 C4）：崩溃后需要从第 1 章重新开始
- 章节内容超过 3000 字符会被硬截断（缺陷 C5）

## 成功校验

1. `chapters.yaml` 存在且列表长度等于 `chapter_index.yaml` 的章节数
2. `outline/structure.yaml` 存在
3. `characters/profiles/` 下有人物小传文件
4. `meta.yaml` 中 `status: analyzed`
5. 终端输出 `分析流水线完成`

## 失败处理

| 症状 | 处理 |
|------|------|
| API 超时 / 连接错误 | 等待 30 秒后重跑 `pipeline.py analyze` |
| `chapters.yaml` 章节数少于 `chapter_index.yaml` | 章级分析中途崩溃，需重跑（会从头开始） |
| 大纲结构不合理 | 大纲基于前 5000 字生成，准确度有限，待代码修复 |
