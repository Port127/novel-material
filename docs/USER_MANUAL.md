# Novel Material V2 - 用户手册

## 目录

1. [系统概述](#1-系统概述)
2. [环境配置](#2-环境配置)
3. [Docker 数据库](#3-docker-数据库)
4. [pgAdmin 使用指南](#4-pgadmin-使用指南)
5. [PostgreSQL 基础操作](#5-postgresql-基础操作)
6. [流水线操作](#6-流水线操作)
7. [检索功能](#7-检索功能)
8. [常见问题](#8-常见问题)

---

## 1. 系统概述

### 1.1 系统定位

Novel Material V2 是一个独立的小说素材管理系统，为多个小说项目提供共享素材检索服务。

### 1.2 数据生命周期

```
原文文件 → 格式清洗 → 章节切分 → 章级分析(LLM) → 向量化 → 骨架分析(LLM) → 同步数据库
    ↓          ↓           ↓            ↓            ↓           ↓            ↓
source.txt  清洗后文本  chapter_index.yaml  chapters.yaml  embeddings  outline/...  PostgreSQL
```

### 1.3 核心数据表

| 表名 | 说明 | 主要字段 |
|------|------|---------|
| `novels` | 小说元信息 | material_id, name, genre, premise |
| `chapters` | 章节分析 | chapter, title, summary, tension_level, chapter_functions |
| `outline_sequences` | 大纲序列 | act, sequence, title, description |
| `outline_beats` | 大纲节拍 | beat, chapter, description, tension |
| `characters` | 人物档案 | name, role, archetype, arc_summary |
| `character_appearances` | 人物出场记录 | character_name, chapter, significance |
| `worldbuilding_entities` | 世界观实体 | entity_type, name, description, importance |

---

## 2. 环境配置

### 2.1 前置要求

- **Docker Desktop**: 用于运行 PostgreSQL + pgvector
- **Python 3.8+**: 用于运行流水线脚本
- **OpenAI API Key**: 用于 LLM 分析和 Embedding 向量化

### 2.2 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt
```

### 2.3 配置 .env 文件

`.env` 文件位于项目根目录，包含所有配置项：

```bash
# ─────────────────────────────────────────────────────────────
# PostgreSQL 配置
# ─────────────────────────────────────────────────────────────
DB_USER=admin
DB_PASSWORD=123qweASD        # 生产环境建议修改为强密码
DB_NAME=novel_material
DATABASE_URL=postgresql://admin:123qweASD@localhost:5432/novel_material

# ─────────────────────────────────────────────────────────────
# pgAdmin 配置（数据库管理界面）
# ─────────────────────────────────────────────────────────────
PGADMIN_EMAIL=admin@novel.internal
PGADMIN_PASSWORD=123qweASD

# ─────────────────────────────────────────────────────────────
# Embedding 模型配置（用于向量化）
# ─────────────────────────────────────────────────────────────
EMBEDDING_PROVIDER=openai     # 可选: openai / bge / local
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1024
EMBEDDING_API_KEY=sk-xxx      # ⚠️ 必须替换为真实 API Key
EMBEDDING_BASE_URL=https://api.openai.com/v1

# ─────────────────────────────────────────────────────────────
# LLM 配置（用于章级分析、骨架分析）
# ─────────────────────────────────────────────────────────────
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-xxx            # ⚠️ 必须替换为真实 API Key
LLM_BASE_URL=https://api.openai.com/v1
LLM_RATE_LIMIT_SECONDS=1      # API 调用间隔（秒）
```

**重要**：`EMBEDDING_API_KEY` 和 `LLM_API_KEY` 必须替换为真实的 OpenAI API Key，否则流水线无法运行。

---

## 3. Docker 数据库

### 3.1 启动数据库

使用 Makefile 命令启动：

```bash
# 启动 PostgreSQL + pgAdmin 容器
make db-up
```

或直接使用 docker compose：

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
# 查看运行中的容器
docker ps

# 输出应包含两个容器：
# novel-material-pg      (PostgreSQL)
# novel-material-pgadmin (pgAdmin)
```

### 3.3 初始化数据库表

首次启动后，需要创建表结构：

```bash
make db-init
```

或直接运行脚本：

```bash
python scripts/core/init_db.py
```

成功输出：
```
已启用 pgvector 扩展，创建所有表和索引
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

首次登录需要添加 PostgreSQL 服务器：

**步骤 1**：左侧面板右键点击 **Servers** → **Register** → **Server**

**步骤 2**：填写连接信息

| 标签页 | 字段 | 值 |
|--------|------|-----|
| **General** | Name | `Novel Material`（随意命名） |
| **Connection** | Host name/address | `postgres` ⚠️ |
| **Connection** | Port | `5432` |
| **Connection** | Maintenance database | `novel_material` |
| **Connection** | Username | `admin` |
| **Connection** | Password | `123qweASD` |

⚠️ **关键**：Host 必须填写 `postgres`（Docker 服务名），不能写 `localhost`！

**步骤 3**：点击 **Save** 保存

连接成功后，左侧面板显示：
```
Servers
  └── Novel Material
      └── Databases
          └── novel_material
              ├── Schemas
              │   └── public
              │       └── Tables  ← 所有表在这里
              │           ├── novels
              │           ├── chapters
              │           ├── characters
              │           └── ...
```

### 4.3 查看表数据

**方法 1：快速查看所有行**

1. 左侧展开 **Tables**
2. 右键点击某个表（如 `novels`）
3. 选择 **View/Edit Data** → **All Rows**

**方法 2：使用 Query Tool**

1. 左侧点击 **novel_material** 数据库
2. 顶部菜单 **Tools** → **Query Tool**
3. 输入 SQL，点击执行按钮（▶️）

### 4.4 Query Tool 常用 SQL

```sql
-- 查看所有小说
SELECT * FROM novels;

-- 查看小说名称和基本信息
SELECT material_id, name, genre, chapter_count, premise FROM novels;

-- 查看章节分析数据
SELECT 
    material_id, 
    chapter, 
    title, 
    tension_level,
    chapter_functions,
    characters_appear
FROM chapters 
ORDER BY chapter;

-- 查看人物档案
SELECT 
    name, 
    role, 
    archetype, 
    arc_summary,
    appearance_count
FROM characters;

-- 查看世界观设定
SELECT 
    entity_type, 
    name, 
    importance, 
    description
FROM worldbuilding_entities;

-- 查看某小说的所有章节
SELECT chapter, title, summary, tension_level
FROM chapters
WHERE material_id = 'nm_novel_20260503_abcd'
ORDER BY chapter;

-- 统计某小说的章节数
SELECT COUNT(*) as total FROM chapters WHERE material_id = 'nm_novel_xxx';

-- 查看高张力章节（张力 ≥ 4）
SELECT chapter, title, tension_level, key_plot_point
FROM chapters
WHERE tension_level >= 4
ORDER BY tension_level DESC;
```

### 4.5 pgAdmin 界面结构说明

```
┌─────────────────────────────────────────────────────────────────┐
│  pgAdmin 4                                                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────────────────────────────────┐ │
│  │ Servers      │  │ Query Tool                              │ │
│  │  └ Novel Mat │  │ ┌──────────────────────────────────────┐ │ │
│  │   Databases  │  │ │ SELECT * FROM novels;                │ │ │
│  │    novel_mat │  │ │                                      │ │ │
│  │     Schemas  │  │ │                                      │ │ │
│  │      public  │  │ └──────────────────────────────────────┘ │ │
│  │       Tables │  │ [▶ Execute] [📊 Graph] [📝 Edit]         │ │
│  │        novel │  │ ┌──────────────────────────────────────┐ │ │
│  │        chapter│  │ │ Results:                             │ │ │
│  │        charac │  │ │ material_id | name | genre | ...     │ │ │
│  │        ...    │  │ │ nm_xxx      | 三体  | [科幻] | ...   │ │ │
│  └──────────────┘  │ └──────────────────────────────────────┘ │ │
│                    └──────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. PostgreSQL 基础操作

### 5.1 进入 psql 命令行

```bash
make db-shell
```

或直接：

```bash
docker exec -it novel-material-pg psql -U admin -d novel_material
```

进入后看到：
```
psql (16.x)
Type "help" for help.

novel_material=# 
```

### 5.2 psql 常用命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `\l` | 列出所有数据库 | `\l` |
| `\c` | 切换数据库 | `\c novel_material` |
| `\dt` | 列出所有表 | `\dt` |
| `\d 表名` | 查看表结构 | `\d novels` |
| `\du` | 列出所有用户 | `\du` |
| `\q` | 退出 psql | `\q` |

### 5.3 SQL 基础语法

**SELECT 查询**
```sql
-- 查询所有列
SELECT * FROM novels;

-- 查询指定列
SELECT name, genre FROM novels;

-- 条件查询
SELECT * FROM chapters WHERE tension_level >= 4;

-- 排序
SELECT * FROM chapters ORDER BY chapter;

-- 限制结果数
SELECT * FROM novels LIMIT 5;

-- 数组包含查询（genre 是数组类型）
SELECT * FROM novels WHERE genre @> ARRAY['科幻'];
```

**INSERT 插入**
```sql
INSERT INTO novels (material_id, name, genre)
VALUES ('nm_novel_20260501_test', '测试小说', ARRAY['玄幻']);
```

**UPDATE 更新**
```sql
UPDATE novels SET name = '新名称' WHERE material_id = 'nm_xxx';
```

**DELETE 删除**
```sql
DELETE FROM novels WHERE material_id = 'nm_xxx';
-- 注意：会级联删除所有关联数据（chapters, characters 等）
```

### 5.4 数组类型查询

PostgreSQL 支持数组类型字段，如 `genre TEXT[]`：

```sql
-- 查询包含 "科幻" 的小说
SELECT * FROM novels WHERE genre @> ARRAY['科幻'];

-- 查询包含多个标签
SELECT * FROM novels WHERE genre @> ARRAY['科幻', '悬疑'];

-- 查询章节功能包含 "开局困境"
SELECT * FROM chapters WHERE chapter_functions @> ARRAY['开局困境'];

-- 查询出场人物包含 "叶文洁"
SELECT * FROM chapters WHERE characters_appear @> ARRAY['叶文洁'];
```

### 5.5 JSONB 类型查询

`psychology` 字段是 JSONB 类型：

```sql
-- 查询人物心理设定中的 fatal_flaw
SELECT name, psychology->>'fatal_flaw' as fatal_flaw
FROM characters;

-- 查询有特定致命缺陷的人物
SELECT * FROM characters 
WHERE psychology->>'fatal_flaw' LIKE '%傲慢%';
```

---

## 6. 流水线操作

### 6.1 流水线概览

| 流水线 | 命令 | 说明 |
|--------|------|------|
| **入库** | `make ingest FILE=<路径>` | 格式清洗 + 章节切分 |
| **完整** | `make full FILE=<路径>` | 入库 → 分析 → 向量 → 精调 → 同步 |
| **分析** | `make analyze ID=<material_id>` | 章级 → 大纲 → 世界观 → 人物 → 标签 |
| **收尾** | `make finalize ID=<material_id>` | 精调 + 同步数据库 |

### 6.2 入库流水线（ingest）

仅执行预处理和章节切分，不调用 LLM：

```bash
make ingest FILE=./my-novel.txt
```

或：

```bash
python scripts/pipeline.py ingest ./my-novel.txt
```

**输出结构**：
```
data/novels/nm_novel_20260503_xxxx/
├── source.txt           # 原文（格式清洗后）
├── chapter_index.yaml   # 章节索引
├── meta.yaml            # 小说元信息
└── chapters/            # 章级分析结果（逐章写入，完成后合并为 chapters.yaml）
```

### 6.3 完整流水线（full）

一键完成所有分析步骤：

```bash
make full FILE=./my-novel.txt
```

**执行顺序**：
```
[1/6] 入库阶段        → 格式清洗、章节切分
[2/6] 章级分析阶段    → LLM 分析每章内容
[3/6] 向量化阶段      → 生成 summary_embedding
[4/6] 骨架分析阶段    → 大纲/世界观/人物/标签
[5/6] 精调阶段        → 人工干预修正
[6/6] 同步数据库阶段  → 写入 PostgreSQL
```

⚠️ **注意**：完整流水线需要 LLM API Key，会消耗 API 费用。

### 6.4 分析流水线（analyze）

对已入库的素材执行分析：

```bash
make analyze ID=nm_novel_20260503_abcd
```

**执行顺序**：
```
[1/5] 章级分析 → 为每章生成摘要、张力、功能等
[2/5] 大纲生成 → 提取幕/序列/节拍结构
[3/5] 世界观提取 → 提取势力/地理/力量体系
[4/5] 人物提取 → 提取人物档案和关系网
[5/5] 标签生成 → 从标签字典中选取标签
```

### 6.5 收尾流水线（finalize）

对已分析的素材执行精调和同步：

```bash
make finalize ID=nm_novel_20260503_abcd
```

**执行顺序**：
```
[1/2] 精调 → 基于 YAML 数据进行人工修正
[2/2] 同步 → 写入 PostgreSQL 数据库
```

### 6.6 流水线数据产物

完整流水线执行后生成的文件：

```
data/novels/nm_novel_20260503_xxxx/
├── source.txt              # 原文
├── chapter_index.yaml      # 章节索引
├── meta.yaml               # 元信息
├── chapters.yaml           # 章级分析（核心）
├── chapter_embeddings.npz  # 向量数据（numpy 压缩格式）
├── outline/                # 大纲分析
│   ├── structure.yaml      # 结构骨架
│   ├── plotlines.yaml      # 情节线
│   ├── hooks_network.yaml  # 钩子网络
│   └── pacing_curve.yaml   # 节奏曲线
├── worldbuilding/          # 世界观
│   ├── _index.yaml         # 索引
│   ├── factions.yaml       # 势力
│   ├── geography.yaml      # 地理
│   └── power_system.yaml   # 力量体系
├── characters/             # 人物
│   ├── _index.yaml         # 人物索引
│   ├── profiles/           # 人物档案
│   │   ├── ye_wenjie.yaml
│   │   └── wang_miao.yaml
│   └── relations.yaml      # 关系网
└── tags.yaml               # 标签汇总
```

---

## 7. 检索功能

### 7.1 检索脚本一览

| 脚本 | 功能 | 示例 |
|------|------|------|
| `search_world.py` | 世界观检索 | `--type faction --genre 修仙` |
| `search_outline.py` | 大纲检索 | `--genre 科幻 --structure 三幕式` |
| `search_detail.py` | 大纲细节检索 | `--genre 悬疑 --act 2` |
| `search_chapter.py` | 章节检索 | `"开局困境写法" --limit 10` |
| `search_character.py` | 人物检索 | `--archetype 导师 --genre 修仙` |
| `search_event.py` | 事件检索 | `"雨中告别" --emotion 悲伤` |

### 7.2 世界观检索

```bash
python scripts/search/search_world.py --type faction --genre 修仙 --limit 10
```

**参数说明**：

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `--type` | 实体类型 | `faction`, `region`, `power_system`, `item` |
| `--genre` | 题材过滤 | `修仙`, `玄幻`, `科幻`, `悬疑` |
| `--importance` | 重要性 | `primary`, `secondary`, `minor` |
| `--name` | 名称关键词 | `宗门`, `门派`, `家族` |
| `--limit` | 返回数量 | `10` |

**输出示例**：
```
找到 5 个世界观设定:

--- 青云宗 (修仙小说A) ---
类型: faction | 重要性: primary
描述: 主角所在的修仙宗门，以剑道为主...

--- 天魔教 (修仙小说B) ---
类型: faction | 重要性: antagonist
描述: 与主角宗门对立的魔道势力...
```

### 7.3 大纲检索

```bash
python scripts/search/search_outline.py --genre 科幻 --structure 三幕式
```

**参数说明**：

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `--genre` | 题材过滤 | `科幻`, `悬疑`, `都市` |
| `--element` | 元素标签 | `重生`, `系统`, `穿越` |
| `--structure` | 叙事结构 | `三幕式`, `英雄之旅` |
| `--query` | 前提关键词 | `废柴逆袭`, `末日求生` |
| `--limit` | 返回数量 | `5` |

### 7.4 章节检索

```bash
python scripts/search/search_chapter.py "开局困境写法" --limit 10
```

**参数说明**：

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `QUERY` | 搜索关键词（必填） | `"开局困境写法"` |
| `--genre` | 题材过滤 | `修仙`, `玄幻` |
| `--function` | 章节功能 | `开局困境`, `高潮`, `转折` |
| `--chapter` | 精确章节号 | `1`, `10` |
| `--tension-min` | 张力最小值 | `3` (范围 1-5) |
| `--tension-max` | 张力最大值 | `5` (范围 1-5) |
| `--limit` | 返回数量 | `10` |

**输出示例**：
```
找到 8 个章节:

--- 第1章: 废柴觉醒 (玄幻小说A) ---
张力: 3 | 功能: [开局困境, 身份揭示]
摘要: 主角林风在家族测试中觉醒废柴天赋...

--- 第3章: 绝境求生 (悬疑小说B) ---
张力: 5 | 功能: [开局困境, 陷阱设置]
摘要: 主角被困密室，必须在10分钟内解谜...
```

### 7.5 人物检索

```bash
python scripts/search/search_character.py --archetype 导师 --genre 修仙
```

**参数说明**：

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `--archetype` | 人物原型 | `英雄`, `导师`, `反派`, `助手` |
| `--role` | 角色类型 | `protagonist`, `antagonist`, `supporting`, `minor` |
| `--genre` | 题材过滤 | `修仙`, `玄幻` |
| `--name` | 名字关键词 | `叶`, `王`, `林` |
| `--limit` | 返回数量 | `10` |

### 7.6 事件检索

```bash
python scripts/search/search_event.py "雨中告别的写法" --emotion 悲伤 --limit 10
```

**参数说明**：

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `QUERY` | 搜索关键词 | `"雨中告别"` |
| `--setting` | 场景类型 | `雨天`, `夜晚`, `密室` |
| `--emotion` | 情绪关键词 | `悲伤`, `愤怒`, `恐惧` |
| `--limit` | 返回数量 | `10` |

---

## 8. 常见问题

### Q1: Docker 容器启动失败

**症状**：`docker-entrypoint.sh: permission denied`

**解决方案**：
```bash
# 清理并重新拉取镜像
docker compose down -v
docker rmi pgvector/pgvector:pg16
docker compose pull
docker compose up -d
```

### Q2: pgAdmin 连接数据库失败

**症状**：`could not connect to server`

**检查项**：
1. Host 是否填写 `postgres`（不是 localhost）
2. 容器是否正常运行：`docker ps`
3. 数据库是否初始化：`make db-init`

### Q3: 流水线执行失败

**症状**：`API Key 无效`

**解决方案**：
检查 `.env` 文件中的 `LLM_API_KEY` 和 `EMBEDDING_API_KEY` 是否为真实有效的 OpenAI API Key。

### Q4: 数据库表找不到

**症状**：pgAdmin 中看不到表

**解决方案**：
执行初始化命令：
```bash
make db-init
```

### Q5: 如何重置数据库

**危险操作**，会删除所有数据：

```bash
make db-reset
```

### Q6: 如何删除某个素材

```bash
make delete-material ID=nm_novel_20260503_abcd
```

或：

```bash
python scripts/utils/material_delete.py --id nm_novel_20260503_abcd
```

删除会级联清理：
- YAML 文件目录
- 数据库中所有关联记录（chapters, characters, worldbuilding 等）
- 全局索引中的引用

### Q7: 如何查看当前有哪些素材

```bash
# 查看 YAML 目录
ls data/novels/

# 或在 psql 中查询
make db-shell
SELECT material_id, name, chapter_count FROM novels;
```

---

## 附录：Makefile 命令速查

```bash
make help        # 显示所有可用命令

# Docker 数据库
make db-up       # 启动容器
make db-down     # 停止容器
make db-init     # 初始化表
make db-shell    # 进入 psql
make db-reset    # 重置数据库

# 流水线
make ingest FILE=<路径>   # 入库
make full FILE=<路径>     # 完整流水线
make analyze ID=<id>      # 分析
make finalize ID=<id>     # 收尾

# 素材管理
make import-material ID=<id>  # 导入
make delete-material ID=<id>  # 删除

# 检索
make search       # 显示检索帮助

# 维护
make validate     # 校验 YAML 格式
make docker-prune # 清理 Docker 资源
```