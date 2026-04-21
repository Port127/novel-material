---
name: novel-stats
description: 生成全书统计报告（情节/转折/节奏/钩子/人物等，含图表）
when_to_use: 事件全部完成后，生成全书统计分析和可视化报告
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

读取所有事件数据，生成全书统计报告，包含表格和图表。

**不读原文，只读 event YAML / manifest / index 数据。**

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 events 已完成
2. 优先读取 `events_manifest.yaml`（如存在）
3. 如需详细数据，分批读取 event YAML 文件

## 输出文件

- `data/novels/{material_id}/stats.yaml` — 原始统计数据
- `data/novels/{material_id}/stats.md` — 轻量可视化报告（Markdown + Mermaid 图表）
- `data/novels/{material_id}/stats.html` — 交互版报告（ECharts 图表 + 人物关系图谱）

## 执行步骤

### 1. 采集事件标签数据

从 manifest 或 event 文件中提取所有标签字段，汇总到内存中。

### 2. 基础统计

| 统计项 | 数据源 | 计算方式 |
|--------|--------|----------|
| 总章节数 | meta.yaml | 直接读取 |
| 总事件数 | events 文件数 | 计数 |
| 平均每章事件数 | 总事件/总章节 | 除法 |
| 事件字数分布 | text_range | 行号差值 |

### 3. 标签分布统计

统计各标签维度中每个值的出现次数和占比，按频率排序：

| 分类 | 维度 |
|------|------|
| 情节 | event_type, conflict, stakes |
| 技法 | technique, dialogue_type, pov, info_delivery |

输出命名为 `{dimension}_distribution`，格式示例：

```yaml
event_type_distribution:
  - type: 日常
    count: 203
    ratio: 0.224
  - type: 争吵
    count: 87
    ratio: 0.096
```

各维度照此模式生成。

### 4. 转折统计

#### 4a. 转折点列表

提取所有 `plot_function` 含 `转折` / `反转` 的事件：

```yaml
turning_points:
  - event: ev_main_005
    chapter: 89
    title: "事件标题"
    type: 转折
  - event: ev_main_015
    chapter: 302
    type: 反转
```

#### 4b. 转折节奏分析

计算相邻转折点之间的章节间距，评估转折节奏：

```yaml
turning_rhythm:
  total_turns: 45
  avg_interval: 23.7    # 平均每 N 章一个转折
  min_interval: 3       # 最密集
  max_interval: 89      # 最稀疏
  rhythm_assessment: "前密后疏，第二幕转折最为密集"
```

### 5. 紧张度曲线

按章聚合 `tension_peak` 值（章内多事件取均值），生成全书紧张度曲线数据。

```yaml
tension_curve:
  - chapter: 1
    avg_tension: 2.0
    max_tension: 2
  - chapter: 2
    avg_tension: 2.5
    max_tension: 3
```

### 6. 节奏分析

统计 `pacing` 各值分布 + 按章节段观察节奏模式：

```yaml
pacing_distribution:
  加速: 150
  减速: 120
  爆发: 80
  喘息: 200
  蓄力: 250
  骤停: 15

pacing_pattern: "整体呈蓄力→爆发→喘息的循环模式，每50章左右一个大周期"
```

### 7. 钩子统计

从 `outline.yaml` 的 `hooks_network` 字段采集钩子数据：

```yaml
hooks_stats:
  # 总体统计
  total_hooks: 45                    # 钩子总数
  verified_hooks: 38                 # 已验证回收
  pending_hooks: 7                   # 待回收
  verification_rate: 0.84            # 验证回收率
  
  # 按类型分布
  by_type:
    道具钩子: 15
    人物钩子: 12
    悬念钩子: 8
    信息钩子: 6
    情感钩子: 4
    
  # 按铆合形式分布
  by_crossing:
    反转铆合: 15                      # 反转铆合（传统"伏笔"）
    因果铆合: 20                      # 因果关联
    悬念铆合: 8                       # 章末悬念
    期待铆合: 7                       # 期待兑现
    
  # 按来源分布
  by_source:
    hooks_field: 30                  # 来自事件 hooks 字段
    plot_function: 15                # 来自 plot_function 反转铆合
    
  # 跨度统计（埋设到回收的章节跨度）
  span_stats:
    avg_span: 234                     # 平均跨度
    longest_span:
      hook_id: hook_007
      planted_chapter: 3
      harvested_chapter: 956
      span: 953
      crossing_type: 反转铆合
    shortest_span:
      hook_id: hook_010
      planted_chapter: 100
      harvested_chapter: 103
      span: 3
      crossing_type: 悬念铆合
      
  # 待回收钩子详情
  pending_details:
    - hook_id: hook_003
      hook_type: 信息钩子
      crossing_type: 反转铆合
      planted_chapter: 12
      detail: '城东的井水最近变苦了'
      confidence: low
```

**数据来源**：
- 从 `outline.yaml` 的 `hooks_network.stats` 读取总体统计
- 从 `hooks_network.chains` 计算跨度分布
- 从 `hooks_network.pending` 提取待回收详情

### 8. 人物统计

```yaml
character_stats:
  total_named: 85         # 有名字的角色总数
  top_appearances:
    - name: 陈汉升
      events: 780
      ratio: 0.86
    - name: 萧容鱼
      events: 234
      ratio: 0.26
  moment_distribution:
    性格展示: 320
    道德抉择: 45
    成长顿悟: 28
```

### 9. 情感统计

```yaml
emotion_stats:
  dominant: [紧张, 温馨, 平静]
  reader_effect_distribution:
    会心一笑: 189
    揪心: 78
    催泪: 45
    爽感: 120
```

### 10. 采集人物关系图谱数据

从 `characters.yaml` 提取关系网数据，构建图谱：

```yaml
relationship_graph:
  nodes:
    - name: "角色名"
      role: protagonist
      faction: "所属阵营"
      events: 780
  edges:
    - from: "角色A"
      to: "角色B"
      type: "恋人"
      weight: 3
```

- **nodes**: 从 `characters.yaml` 的 `roster` 提取，附加出场统计
- **edges**: 从 `characters.yaml` 的 `relations` 提取，weight 为共同出场事件数
- 阵营信息从 `factions` 提取，用于图谱节点着色

### 11. 生成可视化报告 stats.md（轻量版）

使用 Mermaid 图表：

```markdown
# 《{书名}》统计报告

## 基础数据
| 项目 | 数值 |
|------|------|
| 总章节 | 1070 |
| 总事件 | 45 |
| ... | ... |

## 紧张度曲线
(Mermaid xychart-beta 折线图)

## 事件类型分布
(Mermaid pie 饼图)

## 转折节奏
(Mermaid xychart-beta 散点/柱状图)

## 人物出场频率 Top 10
(Mermaid bar 柱状图)

## 情感分布
(Mermaid pie 饼图)

## 钩子网络
(表格：埋设章节 → 回收章节 → 跨度 → 铆合形式)
(饼图：按铆合形式分布)

## 节奏模式
(Mermaid xychart-beta 堆叠图)
```

### 12. 生成交互版报告 stats.html

单文件 HTML，内嵌 ECharts CDN，包含以下交互图表：

**必须包含的图表**：
1. **紧张度曲线** — 折线图（支持缩放、tooltip 显示章节详情）
2. **事件类型分布** — 饼图/环形图
3. **冲突类型分布** — 柱状图
4. **转折节奏** — 散点图（x=章节号，y=转折类型）
5. **人物出场频率 Top 15** — 横向柱状图
6. **情感分布** — 雷达图或饼图
7. **节奏模式** — 堆叠面积图（按章节段）
8. **人物关系图谱** — ECharts Graph 力导向图
   - 节点 = 人物（大小按出场频率，颜色按阵营）
   - 边 = 关系（标签显示关系类型，粗细按 weight）
   - 支持拖拽、缩放、hover 显示详情

**HTML 生成策略**：
- 单文件，所有 CSS/JS 内联（ECharts 通过 CDN 引入）
- 响应式布局，适配桌面和平板
- 深色/浅色主题自适应
- 顶部导航栏快速跳转各图表
- 先检查 `data/novels/{material_id}/` 下是否已有上次生成的 `stats.html`，如果有，读取其 HTML 结构作为模板骨架，只替换数据部分，避免每次从零生成
- 如果是首次生成，按上述 8 个图表逐个构建

### 13. 写入文件

- `stats.yaml` — 所有原始统计数据（含 relationship_graph）
- `stats.md` — 轻量可视化报告（Mermaid）
- `stats.html` — 交互版报告（ECharts + 关系图谱）

### 14. 更新 meta.yaml

```yaml
pipeline:
  stats_generated: true
  stats_at: "2026-04-05T12:00:00Z"
```

## 输出格式

```
✅ 统计报告生成完成

📚 索材：{name}

📊 核心指标：
  事件总数：45
  转折点：{n} 个（平均每 23.7 章一个）
  钩子网络：45 总 / 38 已验证 / 7 待回收（验证率 84%）
  主导情感：紧张、温馨、平静
  紧张度范围：1.5 - 4.8

📄 数据文件：data/novels/{id}/stats.yaml
📄 可视化报告：data/novels/{id}/stats.md
📄 交互报告：data/novels/{id}/stats.html
```

## 注意事项

- 不读原文，只依赖事件标签数据
- 优先使用 manifest/index 减少 token 消耗
- 统计数据必须基于实际标签，不编造
- Mermaid 图表注意数据量控制（紧张度曲线可按10章采样）
- stats.yaml 保留完整数据，stats.md 做适当精简
- stats.html 使用 ECharts CDN（https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js）
- 人物关系图谱数据来源：characters.yaml（roster + relations + factions）+ 事件出场统计
- 钩子统计统一处理反转铆合：从 outline.yaml 的 hooks_network 字段读取，反转铆合即传统"伏笔"
- 钩子网络可视化：按铆合形式分布饼图 + 埋设回收跨度表格

## References

- [event-unit.schema.yaml](../../../docs/schemas/event-unit.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)