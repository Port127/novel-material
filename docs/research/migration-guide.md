# V1 → V2 迁移指南

## 日期
2026-04-28

## 背景

V1 系统围绕"事件拆分"构建，存在以下核心问题：
- 事件边界不可控（"戏剧动作"是文学概念）
- 单本大书事件拆分耗时几百批次
- 大纲/人物/世界观散落在各文件夹，缺乏全局聚合
- 事件检索效果不理想

V2 系统以**章节**为最小分析单元，移除事件拆分，新增章级分析，采用 PostgreSQL + pgvector 支撑千万级跨书检索。

---

## 一、架构差异对比

| 维度 | V1 | V2 | 变化说明 |
|------|----|----|----------|
| **最小分析单元** | 事件 | 章节 | 事件边界不可控 → 章节边界完全可控 |
| **数据库** | SQLite | PostgreSQL + pgvector | 单表查询 → 跨书检索 + 向量搜索 |
| **事件拆分** | 核心流程（几百批次） | 完全移除 | 投入产出比低，检索效果差 |
| **章级分析** | 无 | 核心新增 | 每章摘要+出场人物+功能标签+张力 |
| **大纲/人物/世界观** | 单文件 | 文件夹结构 | 支持复杂设定，粒度自适应 |
| **Source of Truth** | 分散 | YAML 文件 | 数据库是派生查询层，便于版本控制 |
| **检索方式** | YAML 索引 | SQL + 向量搜索 | 性能提升，支持复杂查询 |

---

## 二、数据迁移策略

### 2.1 可直接搬迁的数据

| V1 数据 | V2 对应 | 迁移方式 |
|---------|---------|----------|
| `data/tags.yaml` | `data/tags.yaml` | 直接复制 |
| `docs/tag-system/` | `docs/tag-system/` | 直接复制 |
| `docs/schemas/` | `docs/schemas/` | 调整适配 V2 Schema |
| 格式清洗脚本 | `scripts/core/ingest.py` | 逻辑复用 |
| 章节切分脚本 | `scripts/core/ingest.py` | 逻辑复用 |

### 2.2 需要调整的数据

| V1 数据 | V2 对应 | 调整说明 |
|---------|---------|----------|
| 事件 YAML 文件 | `chapters.yaml` | 放弃事件，改为章级分析 |
| `scenes/` 目录 | 删除 | V2 不需要场景拆分 |
| `plot_index.yaml` | `data/index.yaml` | 简化为素材路由表 |
| `material.db` (SQLite) | PostgreSQL | 需要数据迁移脚本 |

### 2.3 需要重新生成的数据

| 数据 | 原因 |
|------|------|
| 章级分析 (`chapters.yaml`) | V1 没有，V2 新增 |
| Embedding 向量 | V1 可能使用不同模型 |
| PostgreSQL 表数据 | 从 V1 YAML + SQLite 迁移 |

---

## 三、迁移步骤

### Phase 1: 基础设施准备（1-2 天）

1. **安装 PostgreSQL + pgvector**
   ```bash
   # macOS 示例
   brew install postgresql@16
   brew install pgvector
   ```

2. **初始化 V2 数据库**
   ```bash
   cd novel-material-v2
   python scripts/core/init_db.py
   ```

3. **配置环境**
   - 复制 `.env.example` 为 `.env`
   - 填入 PostgreSQL 连接信息
   - 填入 LLM 和 Embedding API 密钥

### Phase 2: 标签体系搬迁（半天）

1. **复制标签字典**
   ```bash
   cp ../novel-material/data/tags.yaml data/tags.yaml
   ```

2. **复制标签体系文档**
   ```bash
   cp -r ../novel-material/docs/tag-system/ docs/tag-system/
   ```

3. **校验标签合法性**
   ```bash
   python scripts/utils/tag_validator.py
   ```

### Phase 3: Schema 适配（1 天）

1. **调整现有 Schema**
   - 对比 V1 `docs/schemas/` 和 V2 `scripts/core/schema.sql`
   - 调整字段差异

2. **创建迁移脚本**
   ```python
   # scripts/utils/migration_v1_to_v2.py
   # 从 V1 YAML + SQLite 迁移到 V2 PostgreSQL
   ```

### Phase 4: 小说数据迁移（按规模）

#### 小规模（3-5 本）

1. **重新入库分析**
   ```bash
   python scripts/pipeline.py full path/to/novel.txt
   ```

2. **验证章级分析质量**
   ```bash
   python scripts/utils/quality_check.py <material_id>
   ```

#### 大规模（已有分析产物的小说）

1. **使用 material-import 导入**
   ```bash
   python scripts/utils/material_import.py path/to/analyzed/novel/
   ```

2. **批量同步数据库**
   ```bash
   python scripts/core/sync_db.py all
   ```

### Phase 5: 检索验证（1-2 天）

1. **测试 6 个检索场景**
   ```bash
   python scripts/search/search_world.py "修仙力量体系"
   python scripts/search/search_outline.py "修仙大纲"
   python scripts/search/search_detail.py "中段推进"
   python scripts/search/search_chapter.py "开局困境" --genre 修仙
   python scripts/search/search_character.py "导师型人物"
   python scripts/search/search_event.py "雨中告别"
   ```

2. **性能测试**
   - 单书检索响应时间
   - 跨书检索响应时间
   - 并发检索测试

---

## 四、风险控制

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| V1 事件数据丢失 | 已分析的事件产物无法复用 | 明确放弃事件，接受重新分析成本 |
| PostgreSQL 安装复杂 | 环境准备延迟 | 提供 Docker 配置作为备选方案 |
| Embedding 模型不一致 | 向量搜索结果质量变化 | 统一使用 BGE-large-zh（中文优化） |
| 章级分析质量不稳定 | 检索精度下降 | 质量校验脚本自动标记低质量章节 |

---

## 五、V1 废弃内容清单

以下内容在 V2 中**明确废弃**，不需要迁移：

| 废弃内容 | 原因 |
|----------|------|
| 事件 YAML 文件 | 事件拆分边界不可控 |
| `scenes/` 目录 | 场景拆分不产生规律 |
| 结构角色标注（转折/高潮） | 定义模糊，无法检验 |
| 张力曲线标注 | Agent 可自行理解 |
| `plot_index.yaml` 详细索引 | 简化为 `data/index.yaml` 路由表 |
| `scripts/core/search.py` | 被 `scripts/search/` 下的 6 个独立脚本替代 |
| `scripts/core/quality_audit.py` | 被 `scripts/utils/quality_check.py` 替代 |

---

## 六、V2 新增功能

| 新增功能 | 说明 |
|----------|------|
| 章级分析 | 每章生成摘要+出场人物+功能标签 |
| PostgreSQL + pgvector | 千万级跨书检索 + 向量搜索 |
| 6 个独立检索脚本 | 按场景专业化检索 |
| 质量校验脚本 | 自动校验章级分析结果和标签合法性 |
| Embedding 工具 | 统一向量化接口（支持 OpenAI/BGE） |

---

## 七、后续优化方向

| 方向 | 优先级 | 说明 |
|------|--------|------|
| 中文全文搜索 | 高 | 集成 pg_jieba 扩展 |
| Embedding 模型优化 | 高 | 测试 BGE-large-zh vs OpenAI |
| 批量入库优化 | 中 | 支持并行处理 |
| 检索结果排序优化 | 中 | 引入多样性排序 |
| 向量数据库迁移 | 低 | 数据量达亿级时评估 Qdrant |
