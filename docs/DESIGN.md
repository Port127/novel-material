# Novel Material 设计文档

## 系统定位

**独立的小说素材管理系统**，为多个小说项目提供共享素材检索服务。

核心价值：
- 素材集中管理，跨项目复用
- 按场景多维标签检索（6 层 19 维）
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

### 索引优先

检索场景时优先查倒排索引（`scenes_index.yaml`），不遍历全部场景文件。
三级回退：倒排索引 → 场景清单 → 遍历场景文件。

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
2. **优先查 `scenes_index.yaml` 倒排索引**，命中候选 scene_id
3. 只读取候选场景的完整 YAML 确认匹配
4. 按匹配度排序返回候选场景

若无倒排索引，退回到遍历 `scenes_manifest.yaml` 或 `scenes/*.yaml`。

示例：
- "恋爱中吵架" → `relationship: 恋人` + `scene_type: 争吵`
- "弱者反杀强者" → `power_dynamic: 翻转` + `scene_type: 对决`
- "催泪但不煽情" → `reader_effect: 催泪` + `technique: 留白`

## 相关文档

- [AGENTS.md](../AGENTS.md) — skill 路由表 + 命令
- [ARCHITECTURE.md](../ARCHITECTURE.md) — 拓扑、数据存储、Pipeline、标签体系、Schema
