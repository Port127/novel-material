# Novel Material V3 - Agent 使用指南

本文档定义 Codex 与通用 Agent 操作本项目的规则。

## 相关文档

- [项目需求](docs/REQUIREMENTS.md)：产品边界、质量目标和不做什么。
- [系统架构](ARCHITECTURE.md)：当前实现、数据流和已知限制。
- [用户手册](docs/USER_MANUAL.md)：完整命令参数和故障排查。
- [文档索引](docs/README.md)：全部现行文档与状态。

## 语言与沟通规范

- 所有面向用户的回复、计划、任务说明、进度更新、分析结论、决策依据、错误说明和新编写的说明性文档默认使用简体中文。
- 内部隐藏推理不会展示；所有对用户可见的推理摘要和判断依据必须使用中文。
- 命令、代码、路径、配置键、字段名、API 名称、模型名称和无法准确翻译的专有名词可以保留原文。
- 用户明确要求使用其他语言时，以用户当前请求为准。

## Git 提交规范

- 提交标题使用 `<type>(<scope>): <中文摘要>`；`scope` 可省略。
- `type` 沿用项目已有的 `feat`、`fix`、`refactor`、`docs`、`test`、`chore`、`skills` 等英文类型。
- 除类型、作用域、代码标识、文件名、命令和技术专名外，提交标题与正文必须使用中文。
- 每次提交必须包含正文，禁止只有标题。
- 正文必须包含“主要改动”和“验证结果”；“背景与目的”“影响范围”根据实际情况填写。
- “主要改动”必须列出具体内容点，不使用“更新代码”“修复问题”等无法审计的笼统描述。
- “验证结果”必须记录执行的测试或检查及其结果；未运行测试时必须明确说明原因。

推荐格式：

```text
<type>(<scope>): <中文摘要>

背景与目的：
- <修改原因，可按需省略本节>

主要改动：
- <具体改动点>
- <具体改动点>

影响范围：
- <兼容性、数据或行为影响，可按需省略本节>

验证结果：
- <执行的命令或检查>
- <通过结果，或未执行测试的原因>
```

## 项目定位

Novel Material V3 是面向外部 Agent 的小说写作参考检索后端：

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

Skills 位于 `.agents/skills/`，是当前宿主的项目入口；`.agents/skills/` 是事实来源，`.claude/skills/` 是由 `scripts/sync_agent_skills.py` 生成的镜像，禁止单独维护镜像内容。执行项目操作时优先使用适用的 Skill，再通过 `nm` CLI 调用服务；不要直接运行 `pipeline/*.py`、`search/*.py` 或 `storage/*.py`。

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
- 搜索默认使用 `quality` 三路召回；Agent 调用时优先加 `--json --mode quality` 并检查 trace。
- `event`、`detail` 已注册主 CLI；七类检索结果只是参考样例，不是事实答案或最终小说内容。
- 人工 Golden Query 基线尚未完成，不得声称混合检索或重排优于 4096 维精确模式。

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
nm pipeline characters <id> [--repair-character NAME]
nm pipeline tags <id>
nm pipeline refine <id>
nm pipeline profile <id>
nm pipeline full <file> [--mode fast|standard|deep]
nm pipeline status <id>
nm pipeline continue <id> [--mode fast|standard|deep]
nm pipeline report <id> [--run-id RUN_ID]
```

### Search

当前公开命令：

```bash
nm search chapter <keyword> [--mode quality|exact] [--json]
nm search event <keyword> [--mode quality|exact] [--json]
nm search outline [--query TEXT] [--genre TEXT] [--json]
nm search character [--name TEXT] [--archetype TEXT] [--role TEXT] [--json]
nm search world <keyword> [--dimension TEXT] [--json]
nm search detail [keyword] [--act N] [--json]
nm search insight <keyword> [--json]
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
nm storage migrate
nm storage init-db
nm storage init-data
nm storage init-tags
nm storage sync [material_id] [--provider NAME] [--window]

nm validate validate [material_id]
nm validate validate --all
nm validate quality <material_id> [--start N] [--end N]
nm validate insights <material_id>
nm validate artifacts <material_id> [--review]
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
