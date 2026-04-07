# Novel Material 设计文档

## 系统定位

**独立的小说素材管理系统**，为多个小说项目提供共享素材检索服务。

核心价值：
- 素材集中管理，跨项目复用
- 按场景多维标签检索（6 层 22 维场景标签 + 7 维小说标签）
- 人物原型与关系网检索
- 标签规范化治理

## 设计原则

### 仓库即记录系统

所有素材、索引、标签均存储在仓库内，Agent 运行时无需外部依赖。

### Skills 作为唯一入口

所有操作通过 skills 封装。用户不直接操作 YAML 文件。
完整 skill 列表见 [AGENTS.md](../AGENTS.md)。

### 每部小说自治

每部小说独立文件夹 `data/novels/{material_id}/`，全局索引为自动汇总视图。
文件夹完整结构见 [ARCHITECTURE.md](../ARCHITECTURE.md)。

### 渐进处理

场景拆分支持 `all` 模式自动循环分批处理全书，也可手动指定章节范围。`meta.yaml` 中 `status` 字段追踪进度：
- `raw` → 仅有原文（可能已格式化）
- `outlined` → 大纲 + 世界观 + 人物已完成
- `tagged` → 场景拆分 + 标签已完成
- `complete` → 场景全部完成，索引已构建
- `refined` → 精调完成，统计报告已生成

### 渐进披露

Layer 1：Skill 元数据（`SKILL.md` frontmatter）
Layer 2：`AGENTS.md` — 稳定路由（≤100行）
Layer 3：`docs/` — 设计、schema、计划
Layer 4：`data/` — 索引、素材存储

### 脚本优先检索

检索场景时**优先调用 `scripts/search.py` 查 SQLite**，LLM 不直接读大索引文件。
三级回退：SQLite 查询 → YAML 倒排索引 → 遍历场景文件。

SQLite（`data/material.db`）是 YAML 的派生产物，可随时从场景文件重建。

### 批次质量保障

场景拆分每批完成后由 `scripts/quality_audit.py` 自动审计：
- 标签多样性、空字段率、摘要去重率、张力分布
- 指标持久化到 `meta.yaml` 的 `scene_batches` 字段
- 全书完成后检测**质量漂移**（前期 vs 后期批次的指标对比）
- 失败批次在 `continue` 恢复时自动重做

## 数据模型

### 素材索引 (`data/index.yaml`)

路由层，记录 material_id → 文件夹路径：

```yaml
materials:
  - id: nm_novel_20260404_a1b2
    type: novel
    name: "《书名》"
    author: 作者名
    folder: data/novels/nm_novel_20260404_a1b2
    status: raw
    added: 2026-04-04
```

### 检索策略

#### 关键词检索 (`material-search`)

匹配 `name`, `summary`, scene `title` 和 `summary`。

#### 多维标签检索 (`material-search-scene`)

1. 解析自然语言需求为标签组合
2. **优先调用 `scripts/search.py` 查 SQLite**，多维度 AND 交集 + 匹配度排序
3. LLM 读取脚本输出的精简结果（只含 top-N 关键字段）
4. 按需读取少量场景 YAML 获取完整上下文

无 SQLite 时退回读 `scenes_index.yaml`；无索引时退回遍历场景文件。

示例：
- "恋爱中吵架" → `relationship: 恋人` + `scene_type: 争吵`
- "弱者反杀强者" → `power_dynamic: 翻转` + `scene_type: 对决`
- "催泪但不煽情" → `reader_effect: 催泪` + `technique: 留白`

## 跨项目集成

### novel 项目对接

本项目（`novel-material`）是 `../novel` 项目的外部素材库。`novel` 通过以下方式访问素材：

**推荐方式（脚本调用）**：
```bash
python ../novel-material/scripts/search.py scene --emotion 悲伤 --interaction 告别 --limit 5
python ../novel-material/scripts/search.py character --archetype 导师
python ../novel-material/scripts/search.py text --query 告别
```

**直接读取**（小规模/无 SQLite 时）：
```
../novel-material/data/index.yaml            # 素材总索引
../novel-material/data/character_index.yaml  # 跨小说人物检索
../novel-material/data/plot_index.yaml       # 跨小说剧情检索
../novel-material/data/tags.yaml             # 标签字典
```

### 借鉴维度映射

`novel` 项目的 `inspiration-log` 使用 5 个借鉴维度，与本项目的标签体系对应关系如下：

| novel 借鉴维度 | novel-material 标签维度 | 说明 |
|---------------|----------------------|------|
| 设定 | `setting` + `scale` + worldbuilding | 空间环境 + 世界观设定 |
| 节奏 | `pacing` + `tension` + `plot_stage` | 节奏型 + 张力值 + 剧情阶段 |
| 冲突 | `conflict` + `stakes` + `power_dynamic` | 冲突类型 + 赌注 + 权力位差 |
| 结构 | `plot_function` + `technique` + `narrative_structure` | 情节功能 + 叙事技法 + 叙事结构 |
| 人物 | `archetype` + `character_moment` + `psychology.*` | 原型 + 弧光时刻 + 心理深度 |

`material-search-context` 在解析写作上下文时使用此映射自动展开检索维度。

### 风格桥接

`novel` 项目管理每部作品的写作风格，`novel-material` 的小说级标签中有对应维度：

| novel 风格需求 | novel-material 标签 |
|---------------|-------------------|
| 文笔参考 | `prose_style`（华丽/朴素/冷叙述/诗化/...） |
| 基调参考 | `tone`（沉重/轻快/冷峻/热血/...） |
| 长板参考 | `writing_strength`（人物塑造/对话/氛围营造/...） |
| 套路参考 | `tropes`（废柴逆袭/扮猪吃虎/重生复仇/...） |

检索场景时可同时用小说级标签缩小范围（如"找一个冷叙述风格的催泪场景"→ 先筛 `prose_style: 冷叙述` 的小说，再在其中检索 `reader_effect: 催泪`）。

## 相关文档

- [AGENTS.md](../AGENTS.md) — skill 路由表 + 命令
- [ARCHITECTURE.md](../ARCHITECTURE.md) — 拓扑、数据存储、Pipeline、标签体系、Schema
