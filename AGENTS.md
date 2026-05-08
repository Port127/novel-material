# Novel Material V2 - Agent 使用指南

本文档定义 LLM Agent（如 Claude Code）操作本项目的规则。

## 项目定位

Novel Material V2 是一个**小说素材管理系统**：

- **入库**：清洗文本、切分章节
- **分析**：LLM 自动提取大纲、世界观、人物、标签
- **存储**：YAML 本地存储 + PostgreSQL 查询层
- **检索**：语义搜索 + 结构化查询

## Agent 工作原则

### 1. 优先级

1. 用户当前请求
2. 本文件（AGENTS.md）
3. ARCHITECTURE.md

### 2. 使用 CLI 而非底层脚本

Agent 应使用 `nm` 命令，而非直接调用 Python 模块。

| 用户意图 | 正确命令 | 错误做法 |
|---------|---------|---------|
| "入库这本小说" | `nm pipeline full ./novel.txt` | 直接调用 `pipeline/ingest.py` |
| "分析 nm_xxx" | `nm pipeline analyze nm_xxx` | 直接调用 `pipeline/outline.py` |
| "搜索修仙宗门" | `nm search world --type faction --genre 修仙` | 直接调用 `search/world.py` |
| "查看标签统计" | `nm tags stats` | 查询数据库 |
| "从断点继续" | `nm pipeline continue nm_xxx` | 手动检查进度 |
| "同步数据库" | `nm storage sync nm_xxx` | 直接调用 `storage/sync.py` |

### 3. Skills 是上层入口

Skills（`.claude/skills/*/SKILL.md`）封装了 CLI 调用，提供更完整的操作流程。Agent 应优先使用 Skills。

### 4. 标签数据源

- ✓ 标签字典存储在 PostgreSQL `tags` 表
- ✓ 使用 `nm tags stats/list/add` 管理标签
- ✓ `data/tags_view.yaml` 是导出视图（人读格式，不参与逻辑）

### 5. 状态流转

```
ingested → clean → analyzed → finalized
```

| 状态 | 含义 | 可执行操作 |
|------|------|-----------|
| `ingested` | 已入库，未清洗 | 等待 |
| `clean` | 已清洗，待分析 | `nm pipeline analyze` |
| `analyzed` | 已分析，待精调 | `nm pipeline refine` |
| `finalized` | 已完成 | `nm storage sync` |

Agent 不应：
- 对 `analyzed` 状态执行 `analyze`（会覆盖）
- 对 `clean` 状态执行 `refine`（无章级数据）

## CLI 命令总览

### Pipeline 命令

```bash
nm pipeline ingest <file>           # 入库：预处理 + 章节切分
nm pipeline analyze <id>            # 章级分析（支持 --start/--end 范围）
nm pipeline outline <id>            # 大纲生成
nm pipeline worldbuilding <id>      # 世界观提取
nm pipeline characters <id>         # 人物提取
nm pipeline tags <id>               # 标签生成
nm pipeline refine <id>             # 精调统计
nm pipeline full <file>             # 完整流水线（入库→分析→骨架→精调）
nm pipeline status <id>             # 查看进度
nm pipeline continue <id>           # 自动从断点继续
```

### Search 命令

```bash
nm search chapter <keyword>         # 章节检索（向量语义）
nm search outline [--query] [--genre]  # 大纲检索
nm search character [--name] [--archetype]  # 人物检索
nm search world <keyword> [--dimension]  # 世界观检索
nm search event <query> [--setting] [--emotion]  # 事件检索
```

### Tags 命令

```bash
nm tags stats                       # 标签统计
nm tags list [--dimension] [--domain]  # 标签列表
nm tags add <dimension> <tag> <domain>  # 添加标签
nm tags remove <dimension> <tag>    # 删除标签
nm tags review [--auto]             # 审核待定标签
nm tags move <dim> <tag> <new_domain>  # 移动标签领域
nm tags set-synonym <dim> <tag> <standard>  # 设置同义词
nm tags export                      # 导出 YAML 视图
nm tags info <dimension> <tag>      # 标签详情
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
nm storage init-data                # 初始化基础数据
nm storage init-tags                # 导入标签字典
nm storage sync <id>                # 同步 YAML → PostgreSQL
nm storage sync-all                 # 同步所有素材
nm storage reset                    # 重置数据库（危险）
```

### Validate 命令

```bash
nm validate schema <id>             # Schema 结构校验
nm validate quality <id>            # 内容质量校验
nm validate all <id>                # 全量校验
```

## 常用操作

### 入库新小说

```
用户: "入库 ./my-novel.txt"

Agent:
1. 检查文件存在
2. 调用 Skill: material-add 或执行 nm pipeline full ./my-novel.txt
3. 等待完成（长篇可能数小时）
4. 检查 nm material list 或 data/novels/{id}/meta.yaml
```

### 分析已入库素材

```
用户: "分析 nm_novel_20260501_abcd"

Agent:
1. 检查 meta.yaml 状态是否为 clean
2. 执行 nm pipeline analyze nm_novel_20260501_abcd
3. 或分步执行：
   nm pipeline outline nm_xxx
   nm pipeline worldbuilding nm_xxx
   nm pipeline characters nm_xxx
   nm pipeline tags nm_xxx
```

### 部分章节分析

```
用户: "只分析 nm_xxx 第 100-200 章"

Agent:
nm pipeline analyze nm_xxx --start 100 --end 200

注意：警告用户后续阶段基于不完整数据生成
```

### 从断点继续

```
用户: "继续 nm_xxx 的分析"

Agent:
1. nm pipeline status nm_xxx（查看进度）
2. nm pipeline continue nm_xxx（自动执行未完成阶段）
```

### 检索素材

```
用户: "找修仙小说的宗门设定"

Agent:
nm search world --type faction --genre 修仙 --limit 10
```

### 精调统计

```
用户: "精调 nm_xxx"

Agent:
nm pipeline refine nm_xxx
nm storage sync nm_xxx
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
   - API Key 无效 → 修复 `.env` 或 `config/providers.yaml`
   - 网络错误 → 重试（有断点续传）
   - `context_length_exceeded` → 检查截断逻辑
3. 修复后执行 `nm pipeline continue`

### 标签校验失败

标签不在字典中时：

1. 添加新标签：`nm tags add element 新标签 xuanhuan --group 设定元素`
2. 或等待频率自动批（出现 ≥3 次自动入库）

### 数据库同步失败

1. 先执行 `nm validate schema <id>`
2. 修复错误后重新 `nm storage sync`

## 容错机制

分析脚本已内置容错，Agent 无需额外处理：

- `context_length_exceeded` 会快速失败（不触发无效重试）
- 每个分析步骤失败时使用默认值继续
- 流程不会因单步失败而中断
- 网络错误自动指数退避重试（最多 8 次）

Agent 只需检查 `meta.yaml` 中的状态字段。

## 模型基准：qwen3.6-plus

本项目以 **qwen3.6-plus** 为基准模型，所有参数设计应以此为参照。

### 模型能力

| 参数 | 数值 | 说明 |
|------|------|------|
| 最大上下文 (context) | 1,000,000 tokens | 输入+输出总上限 |
| 最大输出 (max_tokens) | 65,536 tokens | 单次响应输出上限 |
| 思考预算 (thinking_budget) | 81,920 tokens | 深度思考模式上限 |

### 本项目实际配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `_MAX_CHAPTER_TOKENS` (.env) | 5000 | 单章输入截断上限 |
| `LLM_MAX_TOKENS` (.env) | 8000 | 单章输出兜底上限 |
| 批量 max_tokens_override | `n * 1500` | 10 章批量 = 15000 tokens |
| `thinking_budget` | 4000 | 批量分析启用思考模式 |

### 多服务商配置

支持通过 `config/providers.yaml` 配置多服务商：

```yaml
default_provider: deepseek
providers:
  - name: deepseek
    model: deepseek-chat
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    thinking_format: openai
  - name: qwen
    model: qwen3.6-plus
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    thinking_format: dashscope
```

使用方式：`nm pipeline analyze nm_xxx --provider deepseek`

### 注意事项

- 批量分析已启用 `thinking_budget=4000`，启用 thinking 时不应传 `temperature`
- JSON 解析失败时自动翻倍 `max_tokens` 重试（最多 2 次，上限 65536）
- 单章分析降级后使用 `LLM_MAX_TOKENS` 作为输出上限