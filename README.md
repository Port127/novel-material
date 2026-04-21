# Novel Material

独立的小说素材管理库，为 AI 辅助小说写作系统提供共享素材检索服务。

提供两种使用方式：**Web UI**（可视化管理 + 搜索）和 **Agent CLI**（自动化流水线处理）。

## 功能

- **Web UI**：总览仪表盘、素材详情（大纲/世界观/人物/标签/事件/统计 7 个 tab）、多维标签搜索（支持多选）、全文搜索、人物搜索、标签字典管理、Pipeline 触发、LLM 配置
- **4 段子流水线**：入库清洗 → 骨架分析 → 事件拆分+索引 → 精调+统计
- **外部导入**：支持导入已按 schema 分析好的素材，自动校验+注册+建索引
- **多维标签体系**：6 层 20 维事件标签 + 7 维小说标签，共 418 个标签值
- **SQLite 查询层**：结构化多维检索，支持跨小说搜索事件、人物、全文
- **批次质量审计**：自动检测标签多样性、质量漂移、失败批次
- **跨对话恢复**：长小说事件拆分可跨多次对话，每批进度持久化
- **测试覆盖**：195 个自动化测试（backend 93 + frontend 33 + scripts 69）

## 快速开始

### Web UI

```bash
# 启动后端（端口 5273）
cd backend && pip install -r requirements.txt && python main.py

# 启动前端（端口 5173，自动代理 API 到后端）
cd frontend && npm install && npm run dev
```

打开 http://localhost:5173 即可使用。

### Agent CLI

```bash
# ── 入库一本小说 ──

# 方式 1：全自动（短篇推荐）
/novel-pipeline full /path/to/novel.txt

# 方式 2：分段调用（大书推荐，每次开新对话）
/pipeline-ingest /path/to/novel.txt        # ① 入库+清洗
/pipeline-analyze nm_novel_20260408_xxxx   # ② 大纲+世界观+人物+标签
/pipeline-events nm_novel_20260408_xxxx    # ③ 全书事件（可跨对话恢复）
/pipeline-finalize nm_novel_20260408_xxxx  # ④ 精调+统计报告

# 方式 3：导入已分析好的素材
/material-import /path/to/analyzed_folder

# ── 检索素材 ──

/material-search-event 恋人在雨中告别
python scripts/core/search.py event --event-type 对决 --emotion 燃 --tension-min 4
```

详细使用指南见 [docs/USAGE-GUIDE.md](docs/USAGE-GUIDE.md)。

### 运行测试

```bash
cd backend && python -m pytest tests/            # 后端 93 tests
cd frontend && npm test                           # 前端 33 tests
cd scripts && python -m pytest tests/             # 脚本 69 tests
```

## 与小说项目的关系

本库独立存在，`../novel` 项目通过脚本调用检索素材：

```bash
python ../novel-material/scripts/core/search.py event --emotion 悲伤 --interaction 告别 --limit 5
```

没有本库时，`novel` 项目照常工作，检索精度下降。

## 目录说明

| 目录 | 内容 |
|------|------|
| `frontend/` | React + Vite + Tailwind Web UI |
| `backend/` | FastAPI 后端（API 服务 + Pipeline 调度） |
| `data/novels/` | 每部小说独立文件夹（原文+大纲+人物+事件+索引） |
| `data/index.yaml` | 素材路由表 |
| `data/tags.yaml` | 标签维度字典（20 维事件标签 + 7 维小说标签） |
| `data/material.db` | SQLite 查询索引（从 YAML 派生，可重建） |
| `docs/` | 设计文档、schema 模板、标签指南、使用指南 |
| `scripts/core/` | 预制脚本（检索/索引/校验/审计/清洗） |
| `scripts/generated/` | 运行时自动生成的脚本（已 gitignore） |
| `.claude/skills/` | Agent skill 定义 |

## 关键文档

- [AGENTS.md](AGENTS.md) — Skill 路由表 + 硬规则
- [ARCHITECTURE.md](ARCHITECTURE.md) — 系统拓扑 + 标签体系 + ADR
- [docs/USAGE-GUIDE.md](docs/USAGE-GUIDE.md) — 按事件的使用指南（含数据库查询 + Web UI）
- [docs/TAG_GUIDE.md](docs/TAG_GUIDE.md) — 标签判断依据 + 易混淆对照
