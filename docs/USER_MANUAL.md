# Novel Material V2 - 用户手册

## 目录

1. [系统概述](#1-系统概述)
   - 1.1 系统定位
   - 1.2 用户的两个写作场景
   - 1.3 数据生命周期
   - 1.4 核心数据表
   - 1.5 章节类型
   - 1.6 原文定位
   - 1.7 未实现的检索维度
2. [环境配置](#2-环境配置)
3. [Docker 数据库](#3-docker-数据库)
4. [pgAdmin 使用指南](#4-pgadmin-使用指南)
5. [PostgreSQL 基础操作](#5-postgresql-基础操作)
6. [CLI 入口](#6-cli-入口)
7. [Pipeline 流水线](#7-pipeline-流水线)
8. [Search 检索](#8-search-检索)
9. [Tags 标签管理](#9-tags-标签管理)
10. [Material 素材管理](#10-material-素材管理)
11. [Storage 数据库管理](#11-storage-数据库管理)
12. [Validate 数据校验](#12-validate-数据校验)
13. [标签系统](#13-标签系统)
14. [常见场景](#14-常见场景)
15. [故障排查](#15-故障排查)
16. [容错机制](#16-容错机制)
17. [配置参考](#17-配置参考)
   - .env 必填项
   - 契约文件（优先级最高）
   - config/settings.yaml
   - config/providers.yaml
18. [日志说明](#18-日志说明)

---

## 1. 系统概述

### 1.1 系统定位

novel-material 是一个**小说写作参考检索库**。

它不是用来"学习规律"的训练系统，而是用来**提供检索参考**的素材库。

**类比**：建筑师不会从 100 栋建筑中"学习"如何设计，而是翻阅优秀案例图集，把多个案例的精华组合到自己的设计中。本项目就是那个"案例图集"。

**设计理念**：本项目采用**契约驱动设计**（Contract-Driven Design）。所有校验阈值集中在 `src/novel_material/schema/fields.yaml`，一处修改多处生效（提示词、schema 校验、质量校验）。

### 1.2 用户的两个写作场景

本项目的检索功能服务于两个写作场景：

| 场景 | 阶段 | 需要的检索 | 工作流 |
|------|------|-----------|--------|
| **场景 A：前期规划** | 动笔前构建整体框架 | 世界观、大纲、细纲 | 用户明确需求 → Agent 检索 N 条参考 → 糅合形成自己的设定 |
| **场景 B：章节写作** | 写具体章节时需要参考 | 章纲、人物、事件 | 用户写到某处卡住 → Agent 检索参考 → 糅合写出自己的内容 |

### 1.3 数据生命周期

```
原文文件 → 格式清洗 → 章节切分 → 总体评估(LLM) → 章级分析(LLM) → 向量化 → 骨架分析(LLM) → 精调 → 同步数据库
    ↓          ↓           ↓           ↓             ↓            ↓           ↓            ↓        ↓
source.txt  清洗后文本  chapter_index  evaluation.yaml  chapters.yaml  embeddings  outline/...  infer  PostgreSQL
```

**总体评估**（可选）：5批次采样生成类型/主线/阶段概要，为滑动窗口模式提供上下文。

### 1.4 核心数据表

| 表名 | 说明 | 主要字段 |
|------|------|---------|
| `novels` | 小说元信息 | material_id, name, genre, premise |
| `chapters` | 章节分析 | chapter, title, chapter_type, summary, tension_level, key_event, key_plot_point, emotional_tone, hook_type |
| `outline_sequences` | 大纲序列 | act, sequence, title, description |
| `outline_beats` | 大纲节拍 | beat, chapter, description, tension |
| `characters` | 人物档案 | name, role, archetype, arc_summary |
| `character_appearances` | 人物出场记录 | character_name, chapter, significance |
| `worldbuilding_entities` | 世界观实体 | entity_type, name, description, importance |
| `run_history` | LLM执行统计 | pipeline_name, tokens_in, tokens_out, elapsed_sec |

### 1.5 章节类型

小说中存在非叙事性章节，系统在入库时自动识别类型：

| 类型 | 说明 | 分析策略 |
|------|------|---------|
| `normal` | 正文章节 | 完整分析（摘要、张力、人物、功能） |
| `afterword` | 后记/完本感言 | 放宽分析要求，不参与叙事分析 |
| `extra` | 番外 | 放宽分析要求，不参与叙事分析 |
| `author_note` | 作者说 | 放宽分析要求，不参与叙事分析 |

检索时可将特殊章节类型作为过滤维度。

### 1.6 原文定位

检索结果可追溯到原文具体位置。每个章节分析数据都关联原文的章节号和标题，Agent 可根据检索结果定位到原文进行精确定位。

### 1.7 未实现的检索维度

以下检索维度在代码中存在内部模块（`search/detail.py`），但尚未暴露 CLI 入口：

| 维度 | 说明 | 状态 |
|------|------|------|
| 细纲检索 | 按幕/序列/节拍检索大纲结构 | 内部模块已实现，待 CLI 暴露 |

---

## 2. 环境配置

### 2.1 前置要求

- **Docker Desktop**: 用于运行 PostgreSQL + pgvector
- **Python 3.8+**: 用于运行流水线脚本
- **LLM API Key**: 用于 LLM 分析和 Embedding 向量化（OpenAI 或兼容 API）

### 2.2 安装依赖

```bash
pip install -e .
```

### 2.3 配置 .env 文件

`.env` 文件位于项目根目录，包含所有配置项：

```bash
# ─────────────────────────────────────────────────────────────
# PostgreSQL 配置
# ─────────────────────────────────────────────────────────────
DB_USER=admin
DB_PASSWORD=123qweASD
DB_NAME=novel_material
DATABASE_URL=postgresql://admin:123qweASD@localhost:5432/novel_material

# ─────────────────────────────────────────────────────────────
# pgAdmin 配置
# ─────────────────────────────────────────────────────────────
PGADMIN_EMAIL=admin@novel.internal
PGADMIN_PASSWORD=123qweASD

# ─────────────────────────────────────────────────────────────
# Embedding 模型配置
# ─────────────────────────────────────────────────────────────
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1024
EMBEDDING_API_KEY=sk-xxx      # ⚠️ 必须替换为真实 API Key
EMBEDDING_BASE_URL=https://api.openai.com/v1

# ─────────────────────────────────────────────────────────────
# LLM 配置
# ─────────────────────────────────────────────────────────────
LLM_API_KEY=sk-xxx            # ⚠️ 必须替换为真实 API Key
```

**重要**：`EMBEDDING_API_KEY` 和 `LLM_API_KEY` 必须替换为真实 API Key，否则流水线无法运行。

也可使用多服务商配置（见 [配置参考](#17-配置参考)）。

---

## 3. Docker 数据库

### 3.1 启动数据库

```bash
make db-up      # 启动 PostgreSQL + pgAdmin 容器
```

或：

```bash
docker compose up -d
```

启动成功后输出：
```
▶ 启动数据库...
  PostgreSQL: localhost:5432
  pgAdmin:    http://localhost:5050
```

### 3.2 验证容器状态

```bash
docker ps
# 应包含: novel-material-pg (PostgreSQL) 和 novel-material-pgadmin (pgAdmin)
```

### 3.3 初始化数据库表

首次启动后，创建表结构：

```bash
make db-init
# 或:
nm storage init-db
nm storage init-data
```

成功输出：
```
已创建所有表：novels, chapters, outline, characters, worldbuilding, tags, genre_domain_map, ...
已初始化 22 个一级题材的领域映射
数据库初始化完成!
```

### 3.4 常用命令

| 命令 | 说明 |
|------|------|
| `make db-up` | 启动数据库容器 |
| `make db-down` | 停止数据库容器 |
| `make db-init` | 初始化数据库表 |
| `make db-shell` | 进入 psql 命令行 |
| `make db-reset` | 重置数据库（删除所有数据，危险操作） |
| `make docker-prune` | 清理未使用的 Docker 资源 |

---

## 4. pgAdmin 使用指南

### 4.1 登录 pgAdmin

浏览器访问：**http://localhost:5050**

登录账号：
- **邮箱**: `admin@novel.internal`
- **密码**: `123qweASD`

### 4.2 添加服务器连接

**步骤 1**：左侧面板右键 **Servers** → **Register** → **Server**

**步骤 2**：填写连接信息

| 标签页 | 字段 | 值 |
|--------|------|-----|
| **General** | Name | `Novel Material` |
| **Connection** | Host name/address | `postgres` ⚠️ |
| **Connection** | Port | `5432` |
| **Connection** | Maintenance database | `novel_material` |
| **Connection** | Username | `admin` |
| **Connection** | Password | `123qweASD` |

⚠️ **关键**：Host 必须填写 `postgres`（Docker 服务名），不能写 `localhost`！

**步骤 3**：点击 **Save** 保存

### 4.3 查看表数据

**方法 1**：右键某个表 → **View/Edit Data** → **All Rows**

**方法 2**：顶部菜单 **Tools** → **Query Tool**，输入 SQL 执行

### 4.4 常用 SQL

```sql
-- 查看所有小说
SELECT * FROM novels;

-- 查看高张力章节（张力 ≥ 4）
SELECT chapter, title, tension_level, key_plot_point
FROM chapters WHERE tension_level >= 4 ORDER BY tension_level DESC;

-- 查看人物档案
SELECT name, role, archetype, appearance_count FROM characters;

-- 查看某小说的所有章节
SELECT chapter, title, summary, tension_level
FROM chapters WHERE material_id = 'nm_novel_xxx' ORDER BY chapter;

-- 数组包含查询
SELECT * FROM novels WHERE genre @> ARRAY['科幻'];
```

---

## 5. PostgreSQL 基础操作

### 5.1 进入 psql 命令行

```bash
make db-shell
# 或:
docker exec -it novel-material-pg psql -U admin -d novel_material
```

### 5.2 psql 常用命令

| 命令 | 说明 |
|------|------|
| `\l` | 列出所有数据库 |
| `\c` | 切换数据库 |
| `\dt` | 列出所有表 |
| `\d 表名` | 查看表结构 |
| `\q` | 退出 psql |

### 5.3 数组类型查询

```sql
-- 查询包含 "科幻" 的小说
SELECT * FROM novels WHERE genre @> ARRAY['科幻'];

-- 查询章节功能包含 "开局困境"
SELECT * FROM chapters WHERE chapter_functions @> ARRAY['开局困境'];
```

### 5.4 JSONB 类型查询

```sql
-- 查询人物心理设定中的 fatal_flaw
SELECT name, psychology->>'fatal_flaw' as fatal_flaw FROM characters;
```

---

## 6. CLI 入口

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

## 7. Pipeline 流水线

### nm pipeline ingest

入库单本小说，执行文本清洗和章节切分。

```bash
nm pipeline ingest <file_path>
```

**输出**：
- `data/novels/nm_novel_YYYYMMDD_xxxx/` 目录
- `meta.yaml`（状态：`clean`）
- `chapter_index.yaml`、`source.txt`

### nm pipeline evaluate

总体评估，采样生成小说类型、主线概要、阶段概要。

```bash
nm pipeline evaluate <material_id> [--provider NAME]
```

**参数**：
- `material_id`：素材 ID
- `--provider`：服务商名称（可选）

**输出**：`evaluation.yaml`（位于 `data/novels/{material_id}/`）

**采样策略**：
- 小体量（<200章）：15章分5批，每批3章
- 大体量（≥200章）：50章分5批，每批10章

**用途**：
- 为滑动窗口模式提供全局上下文
- 输出：novel_type、main_thread_summary、core_characters_hint、stage_summaries

**注意**：
- 需要先入库（有 chapter_index.yaml）
- 断点续传：使用 `_evaluation_progress.yaml`

### nm pipeline analyze

章级分析，生成摘要、张力评级、人物出场、章节功能。

```bash
nm pipeline analyze <material_id> [--start N] [--end N] [--provider NAME] [--window]
```

**参数**：
- `material_id`：素材 ID（如 `nm_novel_20260501_abcd`）
- `--start`：起始章节号（可选）
- `--end`：结束章节号（可选）
- `--provider`：服务商名称（可选）
- `--window`：启用滑动窗口模式（需先运行 evaluate）

**滑动窗口模式**（--window）：
- 需要先运行 `nm pipeline evaluate`
- 为每章注入前章摘要 + 全局评估作为上下文
- 新增字段：tension_change、emotion_transition、plot_progress

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

**输出**：`outline/structure.yaml`、`outline/_index.yaml`

### nm pipeline worldbuilding

提取世界观设定（势力、地域、力量体系）。

```bash
nm pipeline worldbuilding <material_id> [--provider NAME]
```

**输出**：`worldbuilding/factions.yaml`、`worldbuilding/regions.yaml`、`worldbuilding/power_systems.yaml`

### nm pipeline characters

提取人物体系（原型、弧线、心理、关系）。

```bash
nm pipeline characters <material_id> [--provider NAME]
```

**输出**：`characters/profiles/*.yaml`、`characters/relations.yaml`

### nm pipeline tags

生成多维标签（element、style、structure、setting）。

```bash
nm pipeline tags <material_id> [--provider NAME]
```

**输出**：`tags.yaml`

### nm pipeline insights

题材感知深度分析，基于已有 `chapters.yaml` 批量生成创作机制分析。

```bash
nm pipeline insights <material_id> [--start N] [--end N] [--provider NAME] [--profile NAME]
```

**参数**：
- `--start/--end`：章节范围
- `--provider`：服务商名称
- `--profile`：显式指定 profile，可重复传入，如 `--profile common --profile suspense`

**输出**：`chapter_insights/{chapter:04d}.yaml`

**注意**：该层是 `chapters.yaml` 之上的深度分析层，不会修改 `chapters.yaml`。

### nm pipeline refine

统计精调，计算出场次数、钩子数等统计信息，并推断结构角色。

```bash
nm pipeline refine <material_id>
```

**执行内容**：
1. 统计精调（出场次数、钩子数）
2. 结构角色推断（调用 infer_key_plot_points）
3. 更新 `meta.yaml` 状态为 `finalized`

**输出**：更新 `outline/_index.yaml`、`characters/profiles/*.yaml`、`meta.yaml`

### nm pipeline full

完整流水线，从入库到精调一步完成。

```bash
nm pipeline full <file_path> [--start N] [--end N] [--provider NAME] [--window] [--mode standard]
```

**执行阶段**：
1. 入库（ingest）
2. 总体评估（evaluate）
3. 章级分析（analyze）
4. 大纲生成（outline）
5. 世界观提取（worldbuilding）
6. 人物提取（characters）
7. 标签生成（tags）
8. 深度分析（insights，standard/deep）
9. 精调（refine）

**运行模式**：
- `fast`：跳过 core insights，优先完成可检索入库
- `standard`：默认模式，完整主流水线 + 批量 core insights
- `deep`：质量优先，预留关键章节 deep insights

**注意**：长篇小说可能耗时数小时，建议先用 `--start 1 --end 10` 测试。

### nm pipeline status

查看流水线进度。

```bash
nm pipeline status <material_id>
```

### nm pipeline continue

自动从断点继续流水线。

```bash
nm pipeline continue <material_id> [--skip-sync] [--start N] [--end N] [--provider NAME] [--window] [--mode standard]
```

**参数**：
- `material_id`：素材 ID
- `--skip-sync`：跳过数据库同步
- `--start/--end`：章级分析范围
- `--provider`：服务商名称
- `--window`：滑动窗口模式
- `--mode`：运行模式，支持 `fast` / `standard` / `deep`

**行为**：
- 检测各阶段完成状态
- 自动执行未完成的阶段
- 支持章级分析断点续传

**行为**：
- 检测各阶段完成状态
- 自动执行未完成的阶段
- 支持章级分析断点续传

---

## 8. Search 检索

检索功能服务于两个写作场景：场景 A（前期规划）使用世界观、大纲、细纲检索；场景 B（章节写作）使用章纲、人物、事件检索。

### nm search chapter

**场景 B** — 找到同类型章节的写法参考。

```bash
nm search chapter <keyword> [--limit N]
```

**返回内容**：章节摘要 + 章节功能标签 + 结构信息

**示例**：
```bash
nm search chapter "主角初次突破" --limit 10
nm search chapter "雨中告别"
```

### nm search outline

**场景 A** — 找到类似类型/结构的大纲作为参考。

```bash
nm search outline [--query TEXT] [--genre TEXT] [--limit N]
```

**返回内容**：完整的大纲结构树（幕 → 序列 → 节拍）

**示例**：
```bash
nm search outline --genre 玄幻 --query "废柴逆袭"
nm search outline --query "复仇" --limit 10
```

### nm search character

**场景 B** — 找到同类人物的塑造参考。

```bash
nm search character [--name TEXT] [--archetype TEXT] [--role TEXT] [--limit N]
```

**返回内容**：人物小传 + 关键出场章节 + 互动模式

**示例**：
```bash
nm search character --archetype 导师
nm search character --role 主角 --limit 20
```

### nm search world

**场景 A** — 找到类似类型/设定的世界观参考。

```bash
nm search world <keyword> [--dimension TEXT] [--limit N]
```

**返回内容**：力量体系结构 + 势力关系图 + 地理空间描述 + 设定亮点

**示例**：
```bash
nm search world "宗门" --dimension faction --limit 10
nm search world "境界" --dimension power_system
```

### nm search event

**场景 B** — 找到同类事件的写法参考。

```bash
nm search event <query> [--setting TEXT] [--emotion TEXT] [--limit N] [--keyword]
```

**返回内容**：匹配的章节摘要 + 上下文信息

**参数**：
- `--keyword`：使用关键词搜索而非向量搜索。适用于精确匹配特定术语或短语的场景。

**示例**：
```bash
nm search event "雨中告别" --setting 城市 --emotion 悲伤
nm search event "主角突破" --limit 20
nm search event "决战" --keyword  # 关键词模式
```

### nm search insight

检索 `chapter_insights/` 中的深度分析结果，不依赖 PostgreSQL。

```bash
nm search insight <keyword> [--limit N]
```

**搜索范围**：`common.conflict`、`common.reader_hook`、`common.writing_takeaway`、`genre.*`

**返回内容**：章节、标题、命中字段、writing_takeaway、素材 ID。

**示例**：
```bash
nm search insight "主角被压制后反杀"
nm search insight "戒指传承" --limit 20
```

---

## 9. Tags 标签管理

### nm tags stats

显示标签统计。

```bash
nm tags stats
```

### nm tags list

列出标签。

```bash
nm tags list [--dimension TEXT] [--domain TEXT] [--limit N]
```

### nm tags add

添加新标签。

```bash
nm tags add <dimension> <tag> <domain> [--group TEXT] [--synonym-of TEXT]
```

**示例**：
```bash
nm tags add element 血脉 xuanhuan --group 设定元素
nm tags add style 热血 common --group 氛围
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

`--auto`：自动审批高频标签（出现 ≥3 次）

### nm tags move

移动标签到其他领域。

```bash
nm tags move <dimension> <tag> <new_domain>
```

### nm tags set-synonym

设置同义词关系。

```bash
nm tags set-synonym <dimension> <tag> <standard_tag>
```

### nm tags export

导出 YAML 视图（人读格式）。

```bash
nm tags export
# 输出: data/tags_view.yaml
```

### nm tags info

查看标签详细信息。

```bash
nm tags info <dimension> <tag>
```

---

## 10. Material 素材管理

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

**使用场景**：从其他实例迁移、导入人工标注素材、恢复备份。

### nm material delete

删除素材及其所有关联资源（危险操作）。

```bash
nm material delete <material_id>
```

**警告**：删除 YAML 文件 + 数据库记录，不可恢复。

### nm material classify

素材分类子命令，对原始素材进行 genre + elements + style + quality 分类。

#### nm material classify status

查看分类进度统计。

```bash
nm material classify status
```

**输出**：总数、已完成、剩余、失败数、预计剩余时间。

#### nm material classify start

启动分类任务（支持断点续传）。

```bash
nm material classify start [--limit N]
```

**参数**：
- `--limit`：限制处理数量，0 表示全部

**执行内容**：
1. 从进度文件恢复断点
2. 分布式采样章节内容
3. LLM 推断 genre_primary / genre_secondary
4. 提取 elements、style、quality
5. 保存到 material_index.yaml

#### nm material classify retry

重试失败的分类任务。

```bash
nm material classify retry [--seq N] [--failed]
```

**参数**：
- `--seq`：重试指定 sequence
- `--failed`：重试所有失败条目

#### nm material classify clean

清空进度文件，重新开始。

```bash
nm material classify clean [--yes]
```

**警告**：清空后需要重新开始分类。

---

## 11. Storage 数据库管理

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

同步 YAML 到 PostgreSQL（支持自动修复）。

```bash
nm storage sync [material_id] [--provider NAME] [--window]
```

**参数**：
- `material_id`：素材 ID（不指定则同步全部）
- `--provider`：服务商名称（用于修复时）
- `--window`：使用滑动窗口模式修复

**自动修复机制**：
- 检测 summary 长度不足等问题章节
- 自动调用 pipeline.analyze 重分析
- 修复成功后继续同步

**示例**：
```bash
nm storage sync nm_xxx                  # 同步单个素材
nm storage sync                         # 同步全部素材
nm storage sync nm_xxx --provider deepseek --window  # 使用指定参数修复
```

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

## 12. Validate 数据校验

### nm validate schema

Schema 结构校验。

```bash
nm validate schema <material_id>
```

**检查项**：`meta.yaml`（material_id 格式、status 合法性）、`chapters.yaml`（章节号、标题、摘要长度、张力范围）、`tags.yaml`（标签白名单校验）

### nm validate quality

内容质量校验。

```bash
nm validate quality <material_id>
```

**检查项**：摘要长度合理性、张力评级一致性、人物出场统计准确性

### nm validate insights

校验 `chapter_insights/` 深度分析结果。

```bash
nm validate insights <material_id>
```

**检查项**：profile 必填字段、字段长度、evidence、confidence、schema_version。

### nm validate all

全量校验。

```bash
nm validate all <material_id>
```

---

## 13. 标签系统

### 13.1 标签体系结构

标签按维度和领域分级，存储在 PostgreSQL 数据库中：

| 维度 | 说明 | 示例 |
|------|------|------|
| **element** | 小说元素 | 血脉、复仇、成长、背叛 |
| **setting** | 世界观体系 | 修真体系、魔法体系、科幻体系 |
| **style** | 叙事风格 | 华丽、朴素、暗黑、热血 |
| **structure** | 叙事结构 | 三幕式、英雄之旅、多线叙事 |

领域分类：
- **common**：通用标签
- **xuanhuan**：玄幻（血脉、飞升、洞天）
- **xianxia**：仙侠（渡劫、宗门、炼丹）
- **dushi**：都市（商战、娱乐圈、神豪）
- **kehuan**：科幻（机甲、星际、丧尸）
- **qihuan**：奇幻（魔法、骑士、精灵）
- **lingyi**：悬疑灵异（诡异、克苏鲁）

### 13.2 动态加载

标签按题材动态加载，避免 LLM prompt 截断：

```
题材: 玄幻
    ↓
加载: common + xuanhuan 相关标签
    ↓
数量: 约 100 个（而非全部 600+）
```

### 13.3 新标签审核

| Level | 标签类型 | 审核方式 |
|-------|---------|---------|
| 0 | hooks/tropes/themes | 自动入库 |
| 1 | element/style | 出现 ≥3 次自动批 |
| 2 | setting/structure | LLM 辅助审核 |
| 3 | genre | 人工审核 |

---

## 14. 常见场景

### 场景 A-1：入库新小说

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

### 场景 A-2：前期规划 — 检索世界观/大纲参考

```bash
# 找修仙类力量体系设计
nm search world "境界" --dimension power_system --limit 10

# 找废柴逆袭类大纲
nm search outline --genre 玄幻 --query "废柴逆袭"

# 找多线叙事的大纲
nm search outline --query "多线叙事"
```

### 场景 B-1：章节写作 — 检索章纲/人物/事件参考

```bash
# 找开局写法
nm search chapter "开局困境" --limit 10

# 找导师型人物写法
nm search character --archetype 导师

# 找雨中告别的写法
nm search event "雨中告别" --setting 城市 --emotion 悲伤
```

### 场景 B-2：部分章节分析

```bash
nm pipeline analyze nm_xxx --start 100 --end 200
# 注意：后续阶段基于不完整数据
nm pipeline continue nm_xxx
```

### 场景 B-3：切换服务商

```bash
nm pipeline analyze nm_xxx --provider deepseek
nm pipeline full ./novel.txt --provider qwen
```

### 场景 B-4：从断点继续

```bash
nm pipeline status nm_xxx   # 检查进度
nm pipeline continue nm_xxx  # 继续执行
nm pipeline continue nm_xxx --skip-sync  # 跳过数据库同步
```

### 场景 A-3：添加和管理标签

```bash
nm tags stats
nm tags add element 道纹 xianxia --group 功法
nm tags set-synonym element 修道者 修士
nm tags review --auto
```

### 场景 A-4：导入外部素材

```bash
nm material import /path/to/nm_novel_20260501_abcd
nm storage sync nm_novel_20260501_abcd
```

---

## 15. 故障排查

### 问题 1：API Key 无效

**症状**：分析立即失败，日志显示 `[AUTH]`

**解决**：检查 `.env` 或 `config/providers.yaml` 中的 API Key 配置。

### 问题 2：速率限制

**症状**：日志显示 `[RATE] 重试 N/8`

**解决**：系统自动处理，无需干预。429 错误会读取 `Retry-After` 响应头。

### 问题 3：上下文超限

**症状**：日志显示 `context_length_exceeded`

**解决**：系统快速失败，不触发无效重试。检查单章截断配置 `_MAX_CHAPTER_TOKENS`。

### 问题 4：章级分析中断

**症状**：分析在某一章停止

**解决**：
```bash
nm pipeline continue nm_xxx
```

### 问题 5：JSON 解析失败

**症状**：日志显示 `[JSON]`

**解决**：系统自动翻倍 max_tokens 重试。多次失败后检查模型输出质量。

### 问题 6：数据库同步失败

**症状**：`nm storage sync` 报错

**解决**：
```bash
nm validate schema nm_xxx  # 先校验 Schema
nm storage sync nm_xxx      # 修复后重新同步
```

### 问题 7：标签不在字典中

**症状**：校验时报错 `标签不在字典中`

**解决**：
```bash
nm tags add element 新标签 xuanhuan
# 或等待频率自动批（出现 ≥3 次）
nm tags review --auto
```

### 问题 8：Docker 容器启动失败

**症状**：`docker-entrypoint.sh: permission denied`

**解决**：
```bash
docker compose down -v
docker rmi pgvector/pgvector:pg16
docker compose pull
docker compose up -d
```

### 问题 9：pgAdmin 连接数据库失败

**症状**：`could not connect to server`

**检查项**：
1. Host 是否填写 `postgres`（不是 localhost）
2. 容器是否正常运行：`docker ps`
3. 数据库是否初始化：`make db-init`

---

## 16. 容错机制

### 16.1 无人值守保障

| 失败场景 | 兜底方案 | 结果 |
|----------|---------|------|
| 前提提炼失败 | `premise="未知"` | 继续流程 |
| 幕/序列生成失败 | `generate_simple_acts()` 简单划分 | 继续流程 |
| 序列 beats 失败 | 跳过该序列 | 继续下一个 |
| 世界观提取失败 | 空结构 | 继续流程 |
| 人物提取失败 | 空列表 | 继续流程 |
| 标签生成失败 | 默认标签 `genre=["其他"]` | 继续流程 |
| 单章分析失败 | 跳过该章 | 继续下一章 |

### 16.2 断点续传

章级分析采用断点续传机制：

```
每章独立存储: chapters/{n:04d}.yaml
    ↓
崩溃恢复: 从最后完成的章节继续
    ↓
全部完成: 合并为 chapters.yaml
```

### 16.3 数据库同步自动修复

sync_novel 检测到 summary 长度不足时自动修复：

```
检测短摘要章节
    ↓
调用 repair_short_summaries 重分析
    ↓
修复成功 → 继续同步
修复失败 → 需人工干预
```

手动触发修复：
```bash
nm storage sync nm_xxx  # 自动检测并修复
```

### 16.4 API 重试策略

| 错误类型 | 重试策略 |
|----------|---------|
| 429（限流） | 优先读取 Retry-After 头，最多 8 次 |
| 5xx（服务端） | 指数退避（4→8→16→…→120s） |
| 网络超时 | 指数退避，最多 8 次 |
| context_length_exceeded | 快速失败（不重试） |

### 16.4 LLM 分析质量动态调节

LLM 在处理长篇小说时，后期输出质量可能下降。系统采用以下防御机制：

| 机制 | 说明 |
|------|------|
| 动态温度调节 | 随批次递增逐步提高 temperature，防止模式化输出 |
| 动态提示词强度 | 每 10 批次唤醒独立性提醒 |
| 输出相似度检测 | 检测 Jaccard 相似度，发现模式化输出时调整策略 |
| Thinking 模式管理 | 前期使用 thinking 模式保证质量，后期关闭 thinking 启用动态温度 |

---

## 17. 配置参考

### .env 必填项

```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
LLM_API_KEY=your_api_key
EMBEDDING_API_KEY=your_api_key
```

### 契约文件（优先级最高）

契约文件是所有校验阈值的**单一数据源**：

| 文件 | 位置 | 说明 |
|------|------|------|
| `fields.yaml` | `src/novel_material/schema/fields.yaml` | 字段定义 + 阈值 |
| `*.yaml` | `src/novel_material/prompts/` | 提示词模板 |

**修改阈值**：直接编辑 `fields.yaml`，修改会自动同步到提示词、schema 校验、质量校验。

```yaml
# fields.yaml 示例
summary:
  description: 章节摘要
  min_length: 50    # 修改此值 → 自动同步到提示词、校验
  max_length: 500
  validate_in: ["prompt", "schema", "quality"]

# 非字段阈值
character_thresholds:
  core: 50      # 核心人物出场章数阈值
  supporting: 10
  minor: 5
```

**提示词引用契约值**：

```yaml
# prompts/analyze.yaml
system_prompt: |
  摘要长度至少 {{summary_min}} 字，最多 {{summary_max}} 字
  # 实际替换为：摘要长度至少 50 字，最多 500 字
```

### config/settings.yaml

非敏感参数配置（受版本控制）：

```yaml
# LLM 请求参数
LLM_MAX_TOKENS: 8000
LLM_TEMPERATURE: 0.3
LLM_RATE_LIMIT_SECONDS: 10

# LLM 批量处理
LLM_CHAPTER_BATCH_SIZE: 10
LLM_MAX_CHAPTER_TOKENS: 5000

# LLM 超时配置（秒）
LLM_ANALYZE_TIMEOUT: 3000
LLM_OUTLINE_TIMEOUT: 3000
LLM_WORLDBUILDING_TIMEOUT: 1800
LLM_CHARACTERS_TIMEOUT: 1800

# 多样性控制
LLM_DYNAMIC_TEMPERATURE_ENABLED: true
LLM_LATE_CHAPTER_THRESHOLD: 0.6
LLM_SIMILARITY_WARNING_THRESHOLD: 0.7
```

详见 `config/settings.yaml`。

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

## 18. 日志说明

### 日志文件位置

`data/novels/{material_id}/pipeline_{date}_{time}_{PID}.log`

**PID 隔离**：并发运行多个 pipeline 时日志写入不同文件。

### 日志格式

```
[material_id] 批次完成: 返回 10/10章...
[material_id 章节分析] API: 12.3s | in=4521 out=823 | finish=stop
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

---

## 附录：CLI 命令速查

```bash
nm --help         # 显示所有命令

# Docker 数据库（Makefile）
make db-up        # 启动容器
make db-down      # 停止容器
make db-init      # 初始化表+数据
make db-shell     # 进入 psql
make db-reset     # 重置数据库

# 流水线
nm pipeline ingest <文件>     # 入库
nm pipeline full <文件>       # 完整流水线
nm pipeline analyze <id>      # 章级分析
nm pipeline outline <id>      # 大纲生成
nm pipeline worldbuilding <id> # 世界观提取
nm pipeline characters <id>   # 人物提取
nm pipeline tags <id>         # 标签生成
nm pipeline refine <id>       # 精调统计
nm pipeline status <id>       # 查看进度
nm pipeline continue <id>     # 断点续传

# 素材管理
nm material import <目录>     # 导入
nm material delete <id>       # 删除
nm material list              # 列出所有素材
nm material classify status   # 分类进度统计
nm material classify start [--limit N]  # 启动分类
nm material classify retry [--seq N]    # 重试失败
nm material classify clean    # 清空进度

# 标签管理
nm tags stats                 # 标签统计
nm tags list                  # 标签列表
nm tags add <dim> <tag> <domain>  # 添加标签
nm tags remove <dim> <tag>    # 删除标签
nm tags review [--auto]       # 审核新标签候选
nm tags export                # 导出 YAML 视图
nm tags set-synonym <dim> <tag> <standard>  # 设置同义词
nm tags move <dim> <tag> <new_domain>  # 移动标签领域

# 检索
nm search chapter <关键词> --limit 10
nm search outline --genre <g> --query <q>
nm search character --archetype <原型>
nm search world <关键词> --dimension <维度>
nm search event <关键词> [--setting <场景>] [--emotion <情绪>]

# 数据库
nm storage init-db            # 初始化表结构
nm storage init-data          # 初始化基础数据
nm storage init-tags          # 导入标签字典
nm storage sync <id>          # 同步 YAML → PostgreSQL
nm storage sync-all           # 同步所有素材
nm storage reset              # 重置数据库（危险）

# 校验
nm validate schema <id>       # Schema 结构校验
nm validate quality <id>      # 内容质量校验
nm validate all <id>          # 全量校验
```
