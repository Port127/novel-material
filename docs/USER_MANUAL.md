# Novel Material V2 - 用户手册

## 目录

1. [系统概述](#1-系统概述)
2. [环境配置](#2-环境配置)
3. [Docker 数据库](#3-docker-数据库)
4. [pgAdmin 使用指南](#4-pgadmin-使用指南)
5. [PostgreSQL 基础操作](#5-postgresql-基础操作)
6. [流水线操作](#6-流水线操作)
7. [标签系统](#7-标签系统)
8. [检索功能](#8-检索功能)
9. [容错机制](#9-容错机制)
10. [常见问题](#10-常见问题)

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
# 安装 Python 包（可编辑模式）
pip install -e .
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

或直接运行 CLI：

```bash
nm storage init-db
nm storage init-data
```

成功输出：
```
已创建所有表：novels, chapters, outline, characters, worldbuilding, tags, genre_domain_map, ...
已初始化 22 个一级题材的领域映射
数据库初始化完成!
```

初始化脚本执行内容：
1. 创建所有表结构（核心表 + 标签表）
2. 插入基础数据（genre_domain_map 22 条题材映射）

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
| **入库** | `nm pipeline ingest <文件>` | 格式清洗 + 章节切分 |
| **完整** | `nm pipeline full <文件>` | 入库 → 分析 → 向量 → 精调 → 同步 |
| **分析** | `nm pipeline analyze <id>` | 章级 → 大纲 → 世界观 → 人物 → 标签 |
| **收尾** | `nm pipeline refine <id>` | 精调 + 同步数据库 |

### 6.2 入库流水线（ingest）

仅执行预处理和章节切分，不调用 LLM：

```bash
nm pipeline ingest ./my-novel.txt
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
nm pipeline full ./my-novel.txt
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
nm pipeline analyze nm_novel_20260503_abcd
```

或单独执行各骨架分析：

```bash
nm pipeline outline nm_novel_20260503_abcd    # 大纲
nm pipeline worldbuilding nm_novel_xxx        # 世界观
nm pipeline characters nm_novel_xxx           # 人物
nm pipeline tags nm_novel_xxx                 # 标签
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
nm pipeline refine nm_novel_20260503_abcd
nm storage sync nm_novel_20260503_abcd
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

## 7. 标签系统

### 7.1 标签体系结构

标签按维度和领域分级，存储在 PostgreSQL 数据库中：

| 维度 | 说明 | 示例 |
|------|------|------|
| **element** | 小说元素 | 血脉、复仇、成长、背叛 |
| **setting** | 世界观体系 | 修真体系、魔法体系、科幻体系 |
| **style** | 叙事风格 | 华丽、朴素、暗黑、热血 |
| **structure** | 叙事结构 | 三幕式、英雄之旅、多线叙事 |

领域分类：
- **common**：通用标签（所有题材共用）
- **xuanhuan**：玄幻专属（血脉、飞升、洞天）
- **xianxia**：仙侠专属（渡劫、宗门、炼丹）
- **dushi**：都市专属（商战、娱乐圈、神豪）
- **kehuan**：科幻专属（机甲、星际、丧尸）
- **qihuan**：奇幻专属（魔法、骑士、精灵）
- **lingyi**：悬疑灵异专属（诡异、克苏鲁）

### 7.2 动态加载

标签按题材动态加载，避免 LLM prompt 截断：

```
题材: 玄幻
    ↓
加载: common + xuanhuan 相关标签
    ↓
数量: 约 100 个（而非全部 600+）
```

### 7.3 标签管理命令

```bash
# 查看标签统计
nm tags stats

# 导出 YAML 视图（人读）
nm tags export

# 添加新标签
nm tags add element 血脉 xuanhuan --group 设定元素

# 删除标签
nm tags remove element 血脉

# 列出所有标签
nm tags list --dimension element

# 审核待定标签
nm tags review
```

### 7.4 新标签审核

新发现的标签会进入候选池，分级审核：

| Level | 标签类型 | 审核方式 |
|-------|---------|---------|
| 0 | hooks/tropes/themes | 自动入库 |
| 1 | element/style | 出现 ≥3 次自动批 |
| 2 | setting/structure | LLM 辅助审核 |
| 3 | genre | 人工审核 |

审核命令：

```bash
# 查看待审核标签
nm tags review

# 自动审批高频标签
nm tags review --auto
```

### 7.5 标签校验

导入素材时会自动校验标签合法性。也可手动校验：

```bash
nm validate --all
```

---

## 8. 检索功能

### 8.1 检索命令一览

使用 `nm search` 进行检索：

```bash
# 大纲检索
nm search outline --genre 科幻 --query "废柴逆袭"

# 章节检索（向量语义搜索）
nm search chapter "开局困境" --limit 10

# 人物检索
nm search character --archetype 导师 --genre 修仙

# 世界观检索
nm search world --type faction --genre 修仙

# 事件检索
nm search event "雨中告别" --limit 10
```

### 8.2 世界观检索

```bash
nm search world --type faction --genre 修仙 --limit 10
```

### 8.3 大纲检索

```bash
nm search outline --genre 科幻 --query "废柴逆袭"
```

### 8.4 章节检索

```bash
nm search chapter "开局困境" --limit 10
```

### 8.5 人物检索

```bash
nm search character --archetype 导师 --genre 修仙
```

### 8.6 事件检索

```bash
nm search event "雨中告别" --limit 10
```

---

## 9. 容错机制

### 9.1 无人值守保障

分析脚本内置容错，支持睡前启动多任务：

| 失败场景 | 兜底方案 | 结果 |
|----------|---------|------|
| 前提提炼失败 | `premise="未知"` | 继续流程 |
| 幕/序列生成失败 | `generate_simple_acts()` 简单划分 | 继续流程 |
| 序列 beats 失败 | 跳过该序列 | 继续下一个 |
| 世界观提取失败 | 空结构 | 继续流程 |
| 人物提取失败 | 空列表 | 继续流程 |
| 标签生成失败 | 默认标签 `genre=["其他"]` | 继续流程 |
| 单章分析失败 | 跳过该章 | 继续下一章 |

### 9.2 断点续传

章级分析采用断点续传机制：

```
每章独立存储: chapters/{n:04d}.yaml
    ↓
崩溃恢复: 从最后完成的章节继续
    ↓
全部完成: 合并为 chapters.yaml
```

执行流程：

```bash
# 第一次执行（分析到第 500 章崩溃）
nm pipeline analyze nm_novel_xxx

# 第二次执行（自动从第 501 章继续）
nm pipeline analyze nm_novel_xxx
# 输出: "断点续传：已完成 500 章，从第 501 章继续"
```

### 9.3 API 重试策略

LLM 调用自动重试：

| 错误类型 | 重试策略 |
|----------|---------|
| 429（限流） | 优先读取 Retry-After 头，最多 8 次 |
| 5xx（服务端） | 指数退避（4→8→16→…→120s） |
| 网络超时 | 指数退避，最多 8 次 |
| context_length_exceeded | 快速失败（不重试） |

### 9.4 检查分析质量

查看 `_index.yaml` 中的质量标记：

```bash
# 查看大纲生成状态
cat data/novels/nm_novel_xxx/outline/_index.yaml
# 输出包含: sequence_failed: 0（无失败）

# 查看世界观提取状态
cat data/novels/nm_novel_xxx/worldbuilding/_index.yaml
# 输出包含: llm_success: true（成功）
```

---

## 10. 常见问题

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
nm material delete --id nm_novel_20260503_abcd
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
nm pipeline ingest <文件>    # 入库
nm pipeline full <文件>      # 完整流水线
nm pipeline analyze <id>     # 分析
nm pipeline refine <id>      # 精调

# 素材管理
nm material import <目录>    # 导入
nm material delete --id <id> # 删除
nm material list             # 列出所有素材

# 标签管理
nm tags stats                # 标签统计
nm tags export               # 导出 YAML 视图
nm tags review               # 审核新标签候选

# 检索
nm search outline --genre <g> --query <q>
nm search chapter <关键词> --limit 10
nm search character --archetype <原型>
nm search world --type <类型>
nm search event <关键词>

# 校验
nm validate --all            # 校验 YAML 格式
```