# Novel Material

独立的小说素材管理库，为 AI 辅助小说写作系统提供共享素材检索服务。

## 功能

- **10 阶段 Pipeline**：入库 → 格式清洗 → 大纲 → 世界观 → 人物 → 标签 → 场景拆分 → 索引 → 精调 → 统计
- **多维标签体系**：6 层 29 维、418 个标签值，覆盖场景内容/人物/情感/结构/技法/物理环境
- **SQLite 查询层**：结构化多维检索，支持跨小说搜索场景、人物、全文
- **批次质量审计**：自动检测标签多样性、质量漂移、失败批次
- **中断恢复**：长小说分批处理，任意时刻断开，新会话接着来

## 快速开始

```bash
# 入库一本小说（全自动 10 阶段）
/novel-pipeline full /path/to/novel.txt

# 找参考场景
/material-search-scene 恋人在雨中告别

# 精确检索（直接调用脚本）
python scripts/search.py scene --scene-type 对决 --emotion 燃 --tension-min 4

# 质量审计
python scripts/quality_audit.py nm_novel_20260405_zhbk --report
```

详细使用指南见 [docs/USAGE-GUIDE.md](docs/USAGE-GUIDE.md)。

## 与小说项目的关系

本库独立存在，`../novel` 项目通过脚本调用检索素材：

```bash
python ../novel-material/scripts/search.py scene --emotion 悲伤 --interaction 告别 --limit 5
```

没有本库时，`novel` 项目照常工作，检索精度下降。

## 目录说明

| 目录 | 内容 |
|------|------|
| `data/novels/` | 每部小说独立文件夹（原文+大纲+人物+场景+索引） |
| `data/index.yaml` | 素材路由表 |
| `data/tags.yaml` | 标签维度字典（6 层 29 维，418 值） |
| `data/material.db` | SQLite 查询索引（从 YAML 派生，可重建） |
| `docs/` | 设计文档、schema 模板、标签指南、使用指南 |
| `scripts/` | 固化脚本（检索/索引/校验/审计） |
| `.claude/skills/` | Agent skill 定义 |

## 关键文档

- [AGENTS.md](AGENTS.md) — Skill 路由表 + 硬规则
- [ARCHITECTURE.md](ARCHITECTURE.md) — 系统拓扑 + 数据层级
- [docs/DESIGN.md](docs/DESIGN.md) — 设计原则 + 检索策略
- [docs/USAGE-GUIDE.md](docs/USAGE-GUIDE.md) — 按场景的使用指南
- [docs/TAG_GUIDE.md](docs/TAG_GUIDE.md) — 标签判断依据 + 易混淆对照
