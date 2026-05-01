# Novel Material V2

小说写作参考检索库。提供跨小说的素材检索服务，帮助创作者在写作前期规划和章节写作阶段快速获取高质量参考样例。

## 定位

不是训练系统，而是**检索参考库**。Agent 自行理解模式，本项目负责检索 + 展示。

## 核心能力

| 场景 | 触发时机 | 返回内容 |
|------|----------|----------|
| 世界观检索 | 前期规划 | 力量体系 + 势力关系 + 地理空间 + 设定亮点 |
| 大纲检索 | 前期规划 | 完整的大纲结构树（幕 → 序列 → 节拍） |
| 细纲检索 | 前期规划 | 序列级/节拍级的结构对比 |
| 章纲检索 | 章节写作 | 章节摘要 + 章节功能标签 + 结构信息 |
| 人物检索 | 人物写作 | 人物小传 + 关键出场章节 + 互动模式 |
| 事件检索 | 事件写作 | 匹配的章节摘要 + 上下文信息 |

## Quick Start

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scripts/core/init_db.py

# 入库新小说
python scripts/pipeline.py ingest path/to/novel.txt

# 检索
python scripts/search/search_chapter.py --query "开局困境写法" --genre 修仙 --limit 10
```

## 目录结构

```
├── scripts/                    # 处理脚本（core/analyze/search/utils）
├── data/                       # 数据（novels/ 索引/标签字典）
├── docs/                       # 文档（schemas/tag-system/research）
├── config/                     # 配置文件
└── .agents/skills/             # Agent 操作手册
```

## 设计原则

1. 以章节为最小分析单元（边界完全可控）
2. 数据用于检索参考，不是学习材料
3. YAML 是 Source of Truth，数据库是派生查询层
4. PostgreSQL + pgvector 支撑千万级检索
