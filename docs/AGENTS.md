# Novel Material V2 - Agent 使用指南

本文档描述 LLM Agent（如 Claude Code）如何正确使用本项目。

## 项目定位

Novel Material V2 是一个**小说素材管理系统**，用于：

1. 入库原始小说文本
2. LLM 自动分析章节结构、人物、世界观、大纲
3. 存储到 PostgreSQL + pgvector 数据库
4. 提供检索服务供其他小说项目调用

## Agent 工作原则

### 1. 使用 Skills 而非直接脚本

Agent 应优先调用 Skills（`.claude/skills/*/SKILL.md`），而非直接执行底层脚本。

| 用户意图 | 正确 Skill | 错误做法 |
|---------|-----------|---------|
| "入库这本小说" | `material-add` | 直接调用 `ingest.py` |
| "分析 nm_xxx" | `pipeline-analyze` | 直接调用 `generate_outline.py` |
| "搜索修仙宗门" | `search` | 直接调用 `search_world.py` |

### 2. 数据库是唯一数据源

**标签系统已迁移到 PostgreSQL**：

- ❌ 不要读取 `data/tags.yaml`（已废弃）
- ✓ 使用 `scripts/tags/load.py` 加载标签
- ✓ 使用 `scripts/tags/validate.py` 校验标签
- ✓ 使用 `scripts/tags/manage.py` 管理标签

### 3. 容错机制

分析脚本已内置容错，Agent 无需额外处理失败场景：

- `context_length_exceeded` 会快速失败（不触发 8 次无用重试）
- 每个分析步骤失败时会使用默认值继续
- 流程不会因单步失败而中断

Agent 只需：
- 检查最终 `_index.yaml` 中的 `llm_success` 字段
- 如果为 `false`，告知用户某步骤失败，但流程已完成

### 4. 状态流转

```
ingested → clean → analyzed → indexed → failed（任意阶段失败）
```

Agent 不应：
- 对 `status: analyzed` 的素材执行 `pipeline-analyze`（会覆盖）
- 对 `status: clean` 的素材执行 `pipeline-finalize`（无章级数据）
- 对 `chapters.yaml` 为空的素材执行 `refine`

## 常用操作模式

### 入库新小说

```
用户: "入库 ./my-novel.txt"

Agent 行为:
1. 检查文件存在
2. 调用 Skill: material-add
3. 执行: python scripts/pipeline.py full ./my-novel.txt
4. 等待完成（可能数小时）
5. 检查 data/novels/{material_id}/meta.yaml 状态
```

### 分析已入库素材

```
用户: "分析 nm_novel_20260501_abcd"

Agent 行为:
1. 检查 meta.yaml 状态是否为 clean
2. 调用 Skill: pipeline-analyze
3. 执行: python scripts/pipeline.py analyze nm_novel_20260501_abcd
```

### 检索素材

```
用户: "找修仙小说的宗门设定"

Agent 行为:
1. 调用 Skill: search
2. 执行: python scripts/search/search_world.py --type faction --genre 修仙
```

## 禁止操作

| 操作 | 原因 |
|------|------|
| 直接修改 `data/tags.yaml` | 已废弃，数据库是唯一数据源 |
| 对同一素材重复执行 `full` | 会覆盖已有分析结果 |
| 在无 `LLM_API_KEY` 时执行分析 | 会立即失败 |
| 手动编辑 `chapters/*.yaml` | 可能破坏断点续传机制 |

## 错误处理

### Pipeline 失败

如果 `meta.yaml` 状态为 `failed`：

1. 查看日志：`data/novels/{material_id}/pipeline.log`
2. 检查错误类型：
   - API Key 无效 → 修复 `.env`
   - 网络错误 → 重试（有断点续传）
   - context_length_exceeded → 检查截断逻辑
3. 修复后重新执行对应流水线

### 标签校验失败

如果 `validate_tag()` 返回 `None`：

1. 标签不在数据库字典中
2. 可选方案：
   - 添加新标签：`python scripts/tags/manage.py add element 新标签 xuanhuan`
   - 或等待频率自动批（出现 ≥3 次自动入库）