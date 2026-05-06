# Novel Material V2

小说素材管理系统，为多个小说项目提供共享素材检索服务。

## 核心功能

- **入库**：自动清洗文本、切分章节、生成索引
- **分析**：LLM 自动分析章节、人物、世界观、大纲结构
- **向量化**：生成语义向量，支持精准检索
- **检索**：世界观、大纲、章节、人物、事件等多维度检索

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

创建 `.env` 文件：

```bash
# PostgreSQL
DATABASE_URL=postgresql://admin:password@localhost:5432/novel_material

# LLM (必须配置)
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini

# Embedding (必须配置)
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-3-small
```

### 3. 启动数据库

```bash
make db-up      # 启动 PostgreSQL + pgAdmin
make db-init    # 初始化表结构
```

### 4. 入库小说

```bash
# 完整流水线（入库 → 分析 → 向量 → 精调 → 同步）
make full FILE=./my-novel.txt

# 或分步执行
make ingest FILE=./my-novel.txt      # 仅入库
make analyze ID=nm_novel_xxx         # 仅分析
make finalize ID=nm_novel_xxx        # 仅收尾
```

### 5. 检索素材

```bash
# 章节检索（语义搜索）
python scripts/search/search_chapter.py "开局困境" --semantic

# 世界观检索
python scripts/search/search_world.py --type faction --genre 修仙

# 人物检索
python scripts/search/search_character.py --archetype 导师 --genre 修仙
```

## Makefile 命令

```bash
make help        # 显示所有命令

# Docker 数据库
make db-up       # 启动容器
make db-down     # 停止容器
make db-init     # 初始化表
make db-shell    # 进入 psql

# 流水线
make ingest FILE=<路径>   # 入库
make full FILE=<路径>     # 完整流水线
make analyze ID=<id>      # 分析
make finalize ID=<id>     # 收尾

# 标签管理
make tags-stats           # 标签统计
make tags-export          # 导出 YAML 视图
make tags-review          # 审核新标签

# 检索
make search               # 显示检索帮助
```

## 数据产物

完整分析后生成的文件结构：

```
data/novels/{material_id}/
├── source.txt              # 原文
├── chapter_index.yaml      # 章节索引
├── meta.yaml               # 元信息
├── chapters.yaml           # 章级分析
├── chapter_embeddings.npz  # 向量数据
├── outline/                # 大纲
│   ├── structure.yaml
│   ├── sequences.yaml
│   └── beats.yaml
├── worldbuilding/          # 世界观
│   ├── factions.yaml
│   ├── geography.yaml
│   └── power_system.yaml
├── characters/             # 人物
│   ├── profiles/
│   └── relationships.yaml
└── tags.yaml               # 标签汇总
```

## 标签系统

标签按题材动态加载，从数据库加载约 100 个相关标签（而非全部 600+）：

- **element**：小说元素（血脉/复仇/成长）
- **setting**：世界观体系（修真/魔法/科幻）
- **style**：叙事风格（华丽/朴素/暗黑）
- **structure**：叙事结构（三幕式/英雄之旅）

新标签自动发现，分级审核入库：
- Level 0：自由标签（hooks/tropes/themes）
- Level 1：频率自动批（出现 ≥3 次）
- Level 2：LLM 辅助审核
- Level 3：人工审核（题材）

## 容错机制

无人值守场景保障：任何步骤失败时使用默认值继续，流程不中断。

- `context_length_exceeded`：快速失败（跳过无用重试）
- 章级分析：断点续传，单章失败跳过
- 骨架分析：每步容错 + 兜底方案

## 文档

- [USER_MANUAL.md](docs/USER_MANUAL.md) - 详细用户手册
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - 系统架构
- [AGENTS.md](docs/AGENTS.md) - LLM Agent 使用指南

## License

MIT