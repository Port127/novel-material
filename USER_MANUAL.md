# Novel Material V2 - 用户手册

本手册提供完整的命令说明和使用场景指南。

## 目录

- [CLI 入口](#cli-入口)
- [Pipeline 流水线](#pipeline-流水线)
- [Search 检索](#search-检索)
- [Tags 标签管理](#tags-标签管理)
- [Material 素材管理](#material-素材管理)
- [Storage 数据库管理](#storage-数据库管理)
- [Validate 数据校验](#validate-数据校验)
- [常见场景](#常见场景)
- [故障排查](#故障排查)

---

## CLI 入口

```bash
nm [命令] [参数]
```

### 主命令

| 命令 | 说明 |
|------|------|
| `nm pipeline` | 数据处理流水线 |
| `nm search` | 素材检索 |
| `nm tags` | 标签管理 |
| `nm material` | 素材管理 |
| `nm storage` | 数据库管理 |
| `nm validate` | 数据校验 |
| `nm version` | 显示版本信息 |

---

## Pipeline 流水线

### nm pipeline ingest

入库单本小说，执行文本清洗和章节切分。

```bash
nm pipeline ingest <file_path>
```

**参数**：
- `file_path`：小说文本文件路径（.txt）

**输出**：
- `data/novels/nm_novel_YYYYMMDD_xxxx/` 目录
- `meta.yaml`（状态：`clean`）
- `chapter_index.yaml`
- `source.txt`

### nm pipeline analyze

章级分析，生成摘要、张力评级、人物出场、章节功能。

```bash
nm pipeline analyze <material_id> [--start N] [--end N] [--provider NAME]
```

**参数**：
- `material_id`：素材 ID（如 `nm_novel_20260501_abcd`）
- `--start`：起始章节号（可选）
- `--end`：结束章节号（可选）
- `--provider`：服务商名称（可选）

**输出**：
- `chapters.yaml` 或 `chapters/{n:04d}.yaml`
- `chapter_embeddings.npz`

**注意**：
- 指定范围时，后续阶段将基于不完整数据
- 有断点续传，崩溃后执行 `nm pipeline continue` 继续

### nm pipeline outline

生成大纲结构（三幕结构 + 序列节拍）。

```bash
nm pipeline outline <material_id> [--provider NAME]
```

**输出**：
- `outline/structure.yaml`
- `outline/_index.yaml`

### nm pipeline worldbuilding

提取世界观设定（势力、地域、力量体系）。

```bash
nm pipeline worldbuilding <material_id> [--provider NAME]
```

**输出**：
- `worldbuilding/factions.yaml`
- `worldbuilding/regions.yaml`
- `worldbuilding/power_systems.yaml`
- `worldbuilding/_index.yaml`

### nm pipeline characters

提取人物体系（原型、弧线、心理、关系）。

```bash
nm pipeline characters <material_id> [--provider NAME]
```

**输出**：
- `characters/profiles/*.yaml`
- `characters/relations.yaml`

### nm pipeline tags

生成多维标签（element、style、structure、setting）。

```bash
nm pipeline tags <material_id> [--provider NAME]
```

**输出**：
- `tags.yaml`

### nm pipeline refine

统计精调，计算出场次数、钩子数等统计信息。

```bash
nm pipeline refine <material_id>
```

**输出**：
- 更新 `outline/_index.yaml`（钩子统计）
- 更新 `characters/profiles/*.yaml`（出场次数）
- 更新 `meta.yaml`（状态：`finalized`）

### nm pipeline full

完整流水线，从入库到精调一步完成。

```bash
nm pipeline full <file_path> [--start N] [--end N] [--provider NAME]
```

**执行阶段**：
1. 入库（ingest）
2. 章级分析（analyze）
3. 大纲生成（outline）
4. 世界观提取（worldbuilding）
5. 人物提取（characters）
6. 标签生成（tags）
7. 精调（refine）

**注意**：
- 长篇小说可能耗时数小时
- 建议先用 `--start 1 --end 10` 测试少量章节

### nm pipeline status

查看流水线进度。

```bash
nm pipeline status <material_id>
```

**输出示例**：
```
素材目录: ✓ 存在
入库状态: ✓ 已入库
章级分析: ✓ 230/230 章完成
大纲生成: ✓ 已完成
世界观提取: ✓ 已完成
人物提取: ✓ 已完成
标签生成: ○ 未完成
精调状态: ○ 未完成
数据库同步: ○ 未同步

下一步: nm pipeline continue nm_novel_20260501_abcd
```

### nm pipeline continue

自动从断点继续流水线。

```bash
nm pipeline continue <material_id> [--skip-sync] [--start N] [--end N] [--provider NAME]
```

**参数**：
- `--skip-sync`：跳过数据库同步
- `--start/--end`：指定章节范围（覆盖已有分析）
- `--provider`：服务商名称

**行为**：
- 检测各阶段完成状态
- 自动执行未完成的阶段
- 支持章级分析断点续传

---

## Search 检索

### nm search chapter

章节检索，基于向量语义搜索。

```bash
nm search chapter <keyword> [--limit N]
```

**参数**：
- `keyword`：关键词或描述
- `--limit`：返回数量（默认 5）

**示例**：
```bash
nm search chapter "主角初次突破" --limit 10
nm search chapter "雨中告别"
```

### nm search outline

大纲检索，基于题材和前提筛选。

```bash
nm search outline [--query TEXT] [--genre TEXT] [--limit N]
```

**参数**：
- `--query`：关键词
- `--genre`：题材筛选（如 `玄幻`、`仙侠`）
- `--limit`：返回数量（默认 5）

**示例**：
```bash
nm search outline --genre 玄幻 --query "废柴逆袭"
nm search outline --query "复仇" --limit 10
```

### nm search character

人物检索，基于原型和角色定位筛选。

```bash
nm search character [--name TEXT] [--archetype TEXT] [--role TEXT] [--limit N]
```

**参数**：
- `--name`：角色名
- `--archetype`：原型类型（如 `导师`、`反派`、`废柴`）
- `--role`：角色定位（如 `主角`、`配角`）
- `--limit`：返回数量（默认 10）

**示例**：
```bash
nm search character --archetype 导师
nm search character --role 主角 --limit 20
nm search character --name "李清风"
```

### nm search world

世界观检索，基于维度筛选。

```bash
nm search world <keyword> [--dimension TEXT] [--limit N]
```

**参数**：
- `keyword`：关键词
- `--dimension`：维度筛选（`faction`、`region`、`power_system`）
- `--limit`：返回数量（默认 5）

**示例**：
```bash
nm search world "宗门" --dimension faction --limit 10
nm search world "境界" --dimension power_system
nm search world "大陆"
```

### nm search event

事件检索，基于场景和情绪过滤。

```bash
nm search event <query> [--setting TEXT] [--emotion TEXT] [--limit N] [--keyword]
```

**参数**：
- `query`：事件描述
- `--setting`：场景类型（如 `城市`、`战场`）
- `--emotion`：情绪基调（如 `悲伤`、`愤怒`）
- `--limit`：返回数量（默认 10）
- `--keyword`：使用关键词搜索而非向量搜索

**示例**：
```bash
nm search event "雨中告别" --setting 城市 --emotion 悲伤
nm search event "主角突破" --limit 20
nm search event "决战" --keyword  # 关键词模式
```

---

## Tags 标签管理

### nm tags stats

显示标签统计。

```bash
nm tags stats
```

**输出**：
```
标签统计表：
| 维度    | 领域     | 数量 |
| element | common   | 50   |
| element | xuanhuan | 80   |
| setting | common   | 30   |
...

同义词: 25 个
```

### nm tags list

列出标签。

```bash
nm tags list [--dimension TEXT] [--domain TEXT] [--limit N]
```

**参数**：
- `--dimension`：维度筛选（`element`、`setting`、`style`、`structure`）
- `--domain`：领域筛选（`common`、`xuanhuan`、`xianxia`）
- `--limit`：显示数量（默认 50）

### nm tags add

添加新标签。

```bash
nm tags add <dimension> <tag> <domain> [--group TEXT] [--synonym-of TEXT]
```

**参数**：
- `dimension`：维度
- `tag`：标签名
- `domain`：适用领域
- `--group`：分组名
- `--synonym-of`：同义词指向（标准标签）

**示例**：
```bash
nm tags add element 血脉 xuanhuan --group 设定元素
nm tags add style 热血 common --group 氛围
nm tags add element 修仙者 xianxia --synonym-of 修士
```

### nm tags remove

删除标签。

```bash
nm tags remove <dimension> <tag>
```

### nm tags review

审核待定标签候选。

```bash
nm tags review [--auto]
```

**参数**：
- `--auto`：自动审批高频标签（出现 ≥3 次）

### nm tags move

移动标签到其他领域。

```bash
nm tags move <dimension> <tag> <new_domain>
```

**示例**：
```bash
nm tags move element 血脉 common
```

### nm tags set-synonym

设置同义词关系。

```bash
nm tags set-synonym <dimension> <tag> <standard_tag>
```

**示例**：
```bash
nm tags set-synonym element 修仙者 修士
```

### nm tags export

导出 YAML 视图（人读格式）。

```bash
nm tags export
```

**输出**：`data/tags_view.yaml`

### nm tags info

查看标签详细信息。

```bash
nm tags info <dimension> <tag>
```

---

## Material 素材管理

### nm material list

列出所有素材。

```bash
nm material list
```

### nm material import

导入外部已分析好的素材目录。

```bash
nm material import <dir>
```

**参数**：
- `dir`：素材目录路径

**使用场景**：
- 从其他 novel-material 实例迁移
- 导入人工标注素材
- 恢复备份

### nm material delete

删除素材及其所有关联资源（危险操作）。

```bash
nm material delete <material_id>
```

**警告**：
- 删除 YAML 文件
- 删除数据库记录
- 不可恢复

---

## Storage 数据库管理

### nm storage init-db

初始化表结构。

```bash
nm storage init-db
```

### nm storage init-data

初始化基础数据（genre_domain_map）。

```bash
nm storage init-data
```

### nm storage init-tags

导入标签字典。

```bash
nm storage init-tags
```

### nm storage sync

同步 YAML 到 PostgreSQL。

```bash
nm storage sync <material_id>
```

**参数**：
- `material_id`：素材 ID

**前置检查**：
- 自动执行 Schema 校验
- 校验失败时中止同步

### nm storage sync-all

同步所有素材。

```bash
nm storage sync-all
```

### nm storage reset

重置数据库（危险操作）。

```bash
nm storage reset
```

---

## Validate 数据校验

### nm validate schema

Schema 结构校验。

```bash
nm validate schema <material_id>
```

**检查项**：
- `meta.yaml`：material_id 格式、status 合法性
- `chapters.yaml`：章节号、标题、摘要长度、张力范围
- `tags.yaml`：标签白名单校验

### nm validate quality

内容质量校验。

```bash
nm validate quality <material_id>
```

**检查项**：
- 摘要长度合理性
- 张力评级一致性
- 人物出场统计准确性

### nm validate all

全量校验。

```bash
nm validate all <material_id>
```

---

## 常见场景

### 场景 1：入库新小说

```bash
# 方法 A：完整流水线（推荐）
nm pipeline full ./my-novel.txt

# 方法 B：分步执行
nm pipeline ingest ./my-novel.txt
nm pipeline analyze nm_novel_20260501_abcd
nm pipeline outline nm_novel_20260501_abcd
nm pipeline worldbuilding nm_novel_20260501_abcd
nm pipeline characters nm_novel_20260501_abcd
nm pipeline tags nm_novel_20260501_abcd
nm pipeline refine nm_novel_20260501_abcd
nm storage sync nm_novel_20260501_abcd
```

### 场景 2：部分章节分析

```bash
# 仅分析第 100-200 章
nm pipeline analyze nm_xxx --start 100 --end 200

# 注意：后续阶段基于不完整数据
nm pipeline continue nm_xxx
# 会警告：大纲等基于不完整章级数据
```

### 场景 3：切换服务商

```bash
# 使用 DeepSeek 服务商
nm pipeline analyze nm_xxx --provider deepseek

# 使用 Qwen 服务商
nm pipeline full ./novel.txt --provider qwen
```

### 场景 4：从断点继续

```bash
# 检查进度
nm pipeline status nm_xxx

# 继续执行
nm pipeline continue nm_xxx

# 如果只想完成剩余骨架分析，跳过数据库同步
nm pipeline continue nm_xxx --skip-sync
```

### 场景 5：检索特定类型内容

```bash
# 检索世界观设定
nm search world "宗门" --dimension faction

# 检索人物原型
nm search character --archetype 导师 --role 配角

# 检索章节（语义搜索）
nm search chapter "主角获得传承"
```

### 场景 6：添加和管理标签

```bash
# 查看统计
nm tags stats

# 添加新标签
nm tags add element 道纹 xianxia --group 功法

# 设置同义词
nm tags set-synonym element 修道者 修士

# 审核待定标签
nm tags review --auto
```

### 场景 7：导入外部素材

```bash
# 从其他实例迁移
nm material import /path/to/nm_novel_20260501_abcd

# 同步到数据库
nm storage sync nm_novel_20260501_abcd
```

---

## 故障排查

### 问题 1：API Key 无效

**症状**：分析立即失败，日志显示 `[AUTH]`

**解决**：
1. 检查 `.env` 中的 `LLM_API_KEY`
2. 或检查 `config/providers.yaml` 中的 `api_key_env` 环境变量

### 问题 2：速率限制

**症状**：日志显示 `[RATE] 重试 N/8`

**解决**：
- 系统自动处理，无需干预
- 429 错误会读取 `Retry-After` 响应头

### 问题 3：上下文超限

**症状**：日志显示 `context_length_exceeded`

**解决**：
- 系统快速失败，不触发无效重试
- 检查单章截断配置 `_MAX_CHAPTER_TOKENS`

### 问题 4：章级分析中断

**症状**：分析在某一章停止

**解决**：
```bash
nm pipeline continue nm_xxx
# 自动从断点继续
```

### 问题 5：JSON 解析失败

**症状**：日志显示 `[JSON]`

**解决**：
- 系统自动翻倍 max_tokens 重试
- 多次失败后检查模型输出质量

### 问题 6：数据库同步失败

**症状**：`nm storage sync` 报错

**解决**：
```bash
# 先校验 Schema
nm validate schema nm_xxx

# 修复错误后重新同步
nm storage sync nm_xxx
```

### 问题 7：标签不在字典中

**症状**：校验时报错 `标签不在字典中`

**解决**：
```bash
# 添加新标签
nm tags add element 新标签 xuanhuan

# 或等待频率自动批（出现 ≥3 次）
nm tags review --auto
```

---

## 配置参考

### .env 必填项

```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
LLM_API_KEY=your_api_key
EMBEDDING_API_KEY=your_api_key
```

### .env 可选项

```bash
LLM_PROVIDER=openai
LLM_MODEL=qwen3.6-plus
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MAX_TOKENS=8000
LLM_TEMPERATURE=0.3
LLM_RATE_LIMIT_SECONDS=60
_MAX_CHAPTER_TOKENS=5000
LLM_CHAPTER_BATCH_SIZE=5
```

### config/settings.yaml

```yaml
LLM_PROVIDER: openai
LLM_MODEL: qwen3.6-plus
LLM_MAX_TOKENS: 8000
LLM_TEMPERATURE: 0.3

# 多样性控制
LLM_DYNAMIC_PROMPT_ENABLED: true
LLM_DIVERSITY_REMINDER_INTERVAL: 10
LLM_LATE_CHAPTER_THRESHOLD: 0.6
LLM_LATE_TEMPERATURE_BOOST: 0.15
LLM_TEMPERATURE_MAX: 0.6
```

### config/providers.yaml

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

---

## 日志说明

### 日志文件位置

`data/novels/{material_id}/pipeline.log`

### 日志格式

```
[章节分析#批次53] API: 12.3s | in=4521 out=823 total=5344 | thinking=1200 | finish=stop
[RATE] 重试 3/8，等待 60s: RateLimitError
[AUTH] API 失败: AuthenticationError
```

### 错误标签

| 标签 | 含义 | 处理建议 |
|------|------|---------|
| `[AUTH]` | 认证错误 | 检查 API Key |
| `[RATE]` | 速率限制 | 自动处理 |
| `[SERVER]` | 服务端错误 | 自动重试 |
| `[TIMEOUT]` | 超时 | 自动重试 |
| `[CONN]` | 连接错误 | 检查网络 |
| `[JSON]` | JSON 解析失败 | 自动翻倍重试 |
| `[HTTP]` | 其他 HTTP 错误 | 检查配置 |