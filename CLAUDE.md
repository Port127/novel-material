# Novel Material V2 - Agent 使用指南

本文档定义 LLM Agent（如 Claude Code）操作本项目的规则。

## 相关文档

- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — 业务边界与不做什么
- [ARCHITECTURE.md](ARCHITECTURE.md) — 系统架构与契约层设计
- [docs/USER_MANUAL.md](docs/USER_MANUAL.md) — 详细使用手册

## 项目定位

Novel Material V2 是一个**小说素材管理系统**：

- **入库**：清洗文本、切分章节
- **分析**：LLM 自动提取大纲、世界观、人物、标签
- **存储**：YAML 本地存储 + PostgreSQL 查询层
- **检索**：语义搜索 + 结构化查询

## 核心架构

### 契约层

```
prompts/  ← 提示词模板（YAML）
schema/   ← 字段契约（fields.yaml）
```

**单一数据源原则**：所有阈值集中在 `schema/fields.yaml`，一处修改多处生效。

### 服务层

```
infra/yaml_io.py        ← YAML 读写
infra/path_service.py   ← 路径构建
infra/progress_manager.py ← 进度管理
infra/context.py        ← 执行上下文
```

Agent 操作应通过 CLI 或服务层，不直接调用底层模块。

## Agent 工作原则

### 1. 优先级

1. 用户当前请求
2. 本文件（AGENTS.md）
3. [ARCHITECTURE.md](ARCHITECTURE.md) — 系统架构
4. [docs/USER_MANUAL.md](docs/USER_MANUAL.md) — 完整命令参考
5. [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — 业务边界

### 2. 使用 CLI 而非底层脚本

Agent 应使用 `nm` 命令，而非直接调用 Python 模块。

| 用户意图 | 正确命令 | 错误做法 |
|---------|---------|---------|
| "入库这本小说" | `nm pipeline full ./novel.txt` | 直接调用 `pipeline/ingest.py` |
| "分析 nm_xxx" | `nm pipeline analyze nm_xxx` | 直接调用 `pipeline/analyze.py` |
| "搜索修仙宗门" | `nm search world "宗门" --dimension faction` | 直接调用 `search/world.py` |
| "从断点继续" | `nm pipeline continue nm_xxx` | 手动检查进度 |

### 3. Skills 是上层入口

Skills（`.claude/skills/*/SKILL.md`）封装了 CLI 调用。Agent 应优先使用 Skills。

### 4. 状态流转

```
ingested/clean → evaluated → analyzed → finalized
```

| 状态 | 含义 | 可执行操作 |
|------|------|-----------|
| `clean` | 已清洗，待评估 | `nm pipeline evaluate`（可选） |
| `evaluated` | 已评估，待分析 | `nm pipeline analyze` |
| `analyzed` | 已分析，待骨架 | `nm pipeline outline/world/char/tags` |
| `finalized` | 已完成 | `nm storage sync` |
| `failed` | 流水线失败 | 查看日志 → `nm pipeline continue` |

**总体评估是可选步骤**：不强制要求，但为滑动窗口模式提供全局上下文。

Agent 不应：
- 对 `analyzed` 状态执行 `analyze`（会覆盖）
- 对 `clean` 状态执行 `refine`（无章级数据）

## CLI 命令速览

> 完整命令参数见 [docs/USER_MANUAL.md](docs/USER_MANUAL.md)。

### Pipeline 命令

```bash
nm pipeline ingest <file>           # 入库：预处理 + 章节切分
nm pipeline evaluate <id>           # 总体评估：类型/主线/阶段概要
nm pipeline analyze <id> [--window] # 章级分析（支持滑动窗口）
nm pipeline outline <id>            # 大纲生成
nm pipeline worldbuilding <id>      # 世界观提取
nm pipeline characters <id>         # 人物提取
nm pipeline tags <id>               # 标签生成
nm pipeline refine <id>             # 精调统计 + 结构推断
nm pipeline full <file>             # 完整流水线
nm pipeline status <id>             # 查看进度
nm pipeline continue <id>           # 自动从断点继续
```

### Search 命令

```bash
nm search chapter <keyword>         # 章节检索（向量语义）
nm search outline [--genre] [--query]  # 大纲检索
nm search character [--archetype]   # 人物检索
nm search world <keyword> [--dimension]  # 世界观检索
nm search event <query> [--setting] [--emotion]  # 事件检索
```

### Tags 命令

```bash
nm tags stats                       # 标签统计
nm tags list [--dimension]          # 标签列表
nm tags add <dimension> <tag> <domain>  # 添加标签
nm tags remove <dimension> <tag>    # 删除标签
nm tags review [--auto]             # 审核待定标签
nm tags export                      # 导出 YAML 视图
```

### Material 命令

```bash
nm material list                    # 素材列表
nm material import <dir>            # 导入已分析素材
nm material delete <id>             # 删除素材（危险）
```

### Storage 命令

```bash
nm storage init-db                  # 初始化表结构
nm storage init-tags                # 导入标签字典
nm storage sync <id>                # 同步 YAML → PostgreSQL
nm storage sync-all                 # 同步所有素材
```

### Validate 命令

```bash
nm validate schema <id>             # Schema 结构校验
nm validate quality <id>            # 内容质量校验
nm validate all <id>                # 全量校验
```

## 常用操作流程

### 入库新小说

```bash
nm pipeline full ./novel.txt
# 或分步执行
nm pipeline ingest ./novel.txt
nm pipeline analyze nm_xxx
nm pipeline outline nm_xxx
nm pipeline worldbuilding nm_xxx
nm pipeline characters nm_xxx
nm pipeline tags nm_xxx
nm pipeline refine nm_xxx
nm storage sync nm_xxx
```

### 从断点继续

```bash
nm pipeline status nm_xxx   # 查看进度
nm pipeline continue nm_xxx  # 继续执行
```

### 检索素材

```bash
nm search chapter "开局困境" --limit 10
nm search character --archetype 导师
nm search world "宗门" --dimension faction
```

## 禁止操作

| 操作 | 原因 |
|------|------|
| 对同一素材重复执行 `full` | 会覆盖已有分析结果 |
| 在无 `LLM_API_KEY` 时执行分析 | 会立即失败 |
| 手动编辑 `chapters/*.yaml` | 可能破坏断点续传机制 |
| 跳过 `nm validate schema` 直接同步 | 可能写入非法数据 |

## 错误处理

### Pipeline 失败

如果 `meta.yaml` 状态为 `failed`：

1. 查看日志：`data/novels/{material_id}/pipeline.log`
2. 检查错误类型：
   - API Key 无效 → 修复 `.env`
   - 网络错误 → 重试（有断点续传）
3. 修复后执行 `nm pipeline continue`

### 标签校验失败

标签不在字典中时：

```bash
nm tags add element 新标签 xuanhuan --group 设定元素
# 或等待频率自动批（出现 ≥3 次自动入库）
nm tags review --auto
```

### 数据库同步失败

```bash
nm validate schema nm_xxx  # 先校验
nm storage sync nm_xxx      # 修复后重新同步
```

## 容错机制

分析脚本已内置容错，Agent 无需额外处理：

- `context_length_exceeded` 会快速失败（不触发无效重试）
- 每个分析步骤失败时使用默认值继续
- 流程不会因单步失败而中断
- 网络错误自动指数退避重试（最多 8 次）

Agent 只需检查 `meta.yaml` 中的状态字段。

## 模型基准

本项目以 **qwen3.6-plus** 为基准模型：

| 参数 | 数值 |
|------|------|
| 最大上下文 | 1,000,000 tokens |
| 最大输出 | 65,536 tokens |

实际配置见 `schema/fields.yaml`（契约层）和 `config/settings.yaml`。

## 章节类型

| 类型 | 说明 | 分析策略 |
|------|------|---------|
| `normal` | 正文章节 | 完整分析 |
| `afterword` | 后记 | 放宽要求 |
| `extra` | 番外 | 放宽要求 |
| `author_note` | 作者说 | 放宽要求 |

## 结构角色字段

两个字段语义不同：

| 字段 | 来源 | 说明 |
|------|------|------|
| key_event | LLM生成 | 关键事件描述（10-30字） |
| key_plot_point | 代码推断 | 结构角色标记 |

key_plot_point 合法值：`inciting_incident`、`first_turning_point`、`midpoint`、`second_turning_point`、`climax`、`resolution`

Agent 不应手动编辑 key_plot_point，由 refine 阶段自动推断。

## 契约层接口

Agent 如需修改阈值，应修改契约文件而非硬编码：

```python
# 修改 schema/fields.yaml
summary:
  min_length: 50  # 修改此值，自动同步到提示词、校验

# 或加载契约
from novel_material.schema import load_field
field = load_field("summary")
print(field.min_length)
```

## LLM 分析质量动态调节

系统内置防御机制：

| 机制 | 说明 |
|------|------|
| 动态温度 | 随批次递增提高 temperature |
| 动态提示词 | 每 10 批次唤醒独立性提醒 |
| 相似度检测 | 检测 Jaccard 相似度 |
| Thinking 管理 | 前期 thinking，后期动态温度 |

Agent 无需干预，只需关注最终状态。