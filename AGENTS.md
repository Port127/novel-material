# Novel Material V2 - Agent 使用指南

本文档定义 Codex 与通用 Agent 操作本项目的规则。

## 相关文档

- [项目需求](docs/REQUIREMENTS.md)：产品边界、质量目标和不做什么。
- [系统架构](ARCHITECTURE.md)：当前实现、数据流和已知限制。
- [用户手册](docs/USER_MANUAL.md)：完整命令参数和故障排查。
- [文档索引](docs/README.md)：全部现行文档与状态。

## 项目定位

Novel Material V2 是小说写作参考检索库：

- 入库：清洗文本并按章切分。
- 分析：提取章节、大纲、人物、世界观、标签和题材洞察。
- 存储：YAML 保存事实数据，PostgreSQL 提供查询层。
- 检索：返回结构化参考，由外部 Agent 负责理解、糅合和生成。

## 工作原则

### 优先级

1. 用户当前请求。
2. 本文件。
3. `docs/REQUIREMENTS.md` 的产品边界。
4. `ARCHITECTURE.md` 的当前技术实现。
5. `docs/USER_MANUAL.md` 的命令说明。

### 使用 Skills 和 CLI

Skills 位于 `.agents/skills/`，是 Agent 的上层入口。执行项目操作时优先使用适用的 Skill，再通过 `nm` CLI 调用服务；不要直接运行 `pipeline/*.py`、`search/*.py` 或 `storage/*.py`。

| 用户意图 | 应使用 | 不应使用 |
|---|---|---|
| 入库小说 | `nm pipeline full ./novel.txt` | 直接调用 `pipeline/ingest.py` |
| 分析素材 | `nm pipeline analyze nm_xxx` | 直接调用 `pipeline/analyze.py` |
| 检索宗门 | `nm search world "宗门" --dimension factions` | 直接调用 `search/world.py` |
| 从断点继续 | `nm pipeline continue nm_xxx` | 手工推断下一阶段 |

### 数据与检索原则

- YAML 是事实来源，PostgreSQL 是可重建的查询层。
- 不手工编辑 `chapters/*.yaml`、`chapter_insights/*.yaml` 或 `key_plot_point`。
- 检索质量优先，不为追求速度擅自降维、替换 embedding 或修改数据库。
- 当前章节搜索默认是关键词匹配；不要把它描述成已经完成的混合检索。
- 内部存在 `event.py`、`detail.py`，但它们没有注册到主 CLI，Agent 不应声称命令可用。

## 状态流转

```text
clean → evaluated（可选）→ analyzed → finalized
  └────────────────────────→ analyzed
任意阶段严重失败 → failed
```

| 状态 | 含义 | 常见下一步 |
|---|---|---|
| `clean` | 已清洗和切分 | `nm pipeline evaluate`（可选）或 `analyze` |
| `evaluated` | 已生成全局评估 | `nm pipeline analyze` |
| `analyzed` | 已完成章级分析 | 骨架分析、insights、refine |
| `finalized` | 已完成精调 | 校验后同步数据库 |
| `failed` | 流水线失败 | 查看日志后执行 `nm pipeline continue` |

总体评估只在滑动窗口等场景需要。insights 是增强层：`fast` 跳过、`standard` 执行 core、`deep` 为更深分析保留扩展点。

## CLI 速览

### Pipeline

```bash
nm pipeline ingest <file>
nm pipeline evaluate <id>
nm pipeline analyze <id> [--window] [--skip-embedding]
nm pipeline insights <id> [--start N] [--end N] [--profile NAME]
nm pipeline outline <id>
nm pipeline worldbuilding <id>
nm pipeline characters <id>
nm pipeline tags <id>
nm pipeline refine <id>
nm pipeline full <file> [--mode fast|standard|deep]
nm pipeline status <id>
nm pipeline continue <id> [--mode fast|standard|deep]
```

### Search

当前公开命令只有：

```bash
nm search chapter <keyword> [--limit N]
nm search outline [--query TEXT] [--genre TEXT] [--limit N]
nm search character [--name TEXT] [--archetype TEXT] [--role TEXT]
nm search world <keyword> [--dimension TEXT] [--limit N]
nm search insight <keyword> [--limit N]
```

### Tags

```bash
nm tags stats
nm tags list [--dimension TEXT]
nm tags add <dimension> <tag> <domain>
nm tags remove <dimension> <tag>
nm tags review [--auto]
nm tags move <dimension> <tag> <domain>
nm tags set-synonym <dimension> <tag> <canonical>
nm tags export
nm tags info <dimension> <tag>
```

### Material

```bash
nm material list
nm material import <directory>
nm material delete --id <material_id> [--force]
nm material classify status
nm material classify start [--limit N]
nm material classify retry [--seq N|--failed]
nm material classify clean
```

### Storage 与 Validate

```bash
nm storage init-db
nm storage init-data
nm storage init-tags
nm storage sync [material_id] [--provider NAME] [--window]

nm validate validate [material_id]
nm validate validate --all
nm validate quality <material_id> [--start N] [--end N]
nm validate insights <material_id>
```

## 常用流程

### 入库并分析

```bash
nm pipeline full ./novel.txt --mode standard
```

分步执行时：

```bash
nm pipeline ingest ./novel.txt
nm pipeline analyze nm_xxx
nm pipeline outline nm_xxx
nm pipeline worldbuilding nm_xxx
nm pipeline characters nm_xxx
nm pipeline tags nm_xxx
nm pipeline insights nm_xxx
nm pipeline refine nm_xxx
nm validate validate nm_xxx
nm storage sync nm_xxx
```

### 从断点继续

```bash
nm pipeline status nm_xxx
nm pipeline continue nm_xxx --mode standard
```

### 检索参考

```bash
nm search chapter "开局困境" --limit 10
nm search character --archetype 导师
nm search world "宗门" --dimension factions
nm search insight "主角被压制后反杀"
```

## 禁止与高风险操作

| 操作 | 原因 |
|---|---|
| 对同一素材重复执行 `pipeline full` | 会创建新素材并重复分析 |
| 无 API Key 时执行 LLM 分析 | 会失败并污染进度判断 |
| 手工修改章节分析文件 | 可能破坏断点续传和校验 |
| 未校验就同步数据库 | 可能写入不完整数据 |
| 未经评测修改 embedding 维度 | 可能降低检索质量并造成全量迁移 |
| 未经用户确认删除素材或重置数据库 | 属于破坏性操作 |

`nm storage sync` 发现短摘要或 schema 问题时可能触发 LLM 修复，产生 API 消耗并修改 YAML。执行前应告知用户这一副作用。

## 错误处理

### Pipeline 失败

1. 查看 `data/novels/{material_id}/pipeline.log` 和 `meta.yaml`。
2. 修复 API Key、网络或数据问题。
3. 执行 `nm pipeline continue <id>`，不要手工跳阶段。

### 数据库同步失败

```bash
nm validate validate nm_xxx
nm validate quality nm_xxx
nm storage sync nm_xxx
```

### 标签不在字典

```bash
nm tags add element 新标签 xuanhuan --group 设定元素
nm tags review --auto
```

## 配置与契约

- 当前 LLM 服务商和模型：`config/providers.yaml`。
- 通用参数：`config/settings.yaml`。
- 字段契约：`src/novel_material/schema/fields.yaml`。
- 提示词模板：`src/novel_material/prompts/`。
- Embedding 配置：`.env`，当前实现位于 `src/novel_material/infra/embedding.py`。

不得在业务代码或文档中重复硬编码契约阈值和当前模型版本。

## 章节字段约束

| 字段 | 来源 | 含义 |
|---|---|---|
| `key_event` | LLM | 关键事件描述 |
| `key_plot_point` | 代码推断 | 粗粒度结构角色 |

`key_plot_point` 由 refine 阶段推断，Agent 不应手工编辑。

章节类型包括 `normal`、`afterword`、`extra`、`author_note`；特殊章节会放宽叙事分析要求。
