---
name: novel-stats
description: 生成全书统计报告（情节/转折/节奏/伏笔/人物等，含图表）
when_to_use: 场景全部完成后，生成全书统计分析和可视化报告
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

读取所有场景数据，生成全书统计报告，包含表格和图表。

**不读原文，只读 scene YAML / manifest / index 数据。**

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 scenes 已完成
2. 优先读取 `scenes_manifest.yaml`（如存在）
3. 如需详细数据，分批读取 scene YAML 文件

## 输出文件

- `data/novels/{material_id}/stats.yaml` — 原始统计数据
- `data/novels/{material_id}/stats.md` — 可视化报告（Markdown + Mermaid 图表）

## 执行步骤

### 1. 采集场景标签数据

从 manifest 或 scene 文件中提取所有标签字段，汇总到内存中。

### 2. 基础统计

| 统计项 | 数据源 | 计算方式 |
|--------|--------|----------|
| 总章节数 | meta.yaml | 直接读取 |
| 总场景数 | scenes 文件数 | 计数 |
| 平均每章场景数 | 总场景/总章节 | 除法 |
| 场景字数分布 | text_range | 行号差值 |

### 3. 情节统计

#### 3a. 场景类型分布

统计 `scene_type` 各值出现次数和占比，按频率排序。

```yaml
scene_type_distribution:
  - type: 日常
    count: 203
    ratio: 0.224
  - type: 争吵
    count: 87
    ratio: 0.096
```

#### 3b. 冲突类型分布

统计 `conflict` 各值出现次数和占比。

#### 3c. 赌注/风险分布

统计 `stakes` 各值出现次数和占比。

### 4. 转折统计

#### 4a. 转折点列表

提取所有 `plot_function` 含 `转折` / `反转` 的场景：

```yaml
turning_points:
  - scene: ch89_s01
    chapter: 89
    title: "场景标题"
    type: 转折
  - scene: ch302_s01
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

按章聚合 `tension` 值（章内多场景取均值），生成全书紧张度曲线数据。

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

### 7. 伏笔统计

```yaml
foreshadowing_stats:
  total_plants: 45        # 伏笔埋设总数
  total_payoffs: 38       # 伏笔回收总数
  unresolved: 7           # 未回收的伏笔
  avg_span: 234           # 埋设到回收的平均章节跨度
  longest_span:
    plant: ch03_s02
    payoff: ch956_s01
    span: 953
  shortest_span:
    plant: ch100_s01
    payoff: ch103_s02
    span: 3
```

### 8. 人物统计

```yaml
character_stats:
  total_named: 85         # 有名字的角色总数
  top_appearances:
    - name: 陈汉升
      scenes: 780
      ratio: 0.86
    - name: 萧容鱼
      scenes: 234
      ratio: 0.26
  character_moment_distribution:
    性格展示: 320
    道德抉择: 45
    成长顿悟: 28
    内心独白: 156
```

### 9. 技法统计

统计 `technique`、`dialogue_type`、`pov`、`info_delivery` 的分布。

### 10. 情感统计

```yaml
emotion_stats:
  dominant_emotions: [紧张, 温馨, 平静]
  reader_effect_distribution:
    会心一笑: 189
    揪心: 78
    催泪: 45
    爽感: 120
```

### 11. 生成可视化报告 stats.md

使用 Mermaid 图表：

```markdown
# 《{书名}》统计报告

## 基础数据
| 项目 | 数值 |
|------|------|
| 总章节 | 1070 |
| 总场景 | 907 |
| ... | ... |

## 紧张度曲线
(Mermaid xychart-beta 折线图)

## 场景类型分布
(Mermaid pie 饼图)

## 转折节奏
(Mermaid xychart-beta 散点/柱状图)

## 人物出场频率 Top 10
(Mermaid bar 柱状图)

## 情感分布
(Mermaid pie 饼图)

## 伏笔网络
(表格：埋设章节 → 回收章节 → 跨度)

## 节奏模式
(Mermaid xychart-beta 堆叠图)
```

### 12. 写入文件

- `stats.yaml` — 所有原始统计数据
- `stats.md` — 可视化报告

### 13. 更新 meta.yaml

```yaml
pipeline:
  stats_generated: true
  stats_at: "2026-04-05T12:00:00Z"
```

## 输出格式

```
✅ 统计报告生成完成

📚 素材：{name}

📊 核心指标：
  场景总数：907
  转折点：45 个（平均每 23.7 章一个）
  伏笔：45 埋 / 38 收 / 7 未回收
  主导情感：紧张、温馨、平静
  紧张度范围：1.5 - 4.8

📄 数据文件：data/novels/{id}/stats.yaml
📄 可视化报告：data/novels/{id}/stats.md
```

## 注意事项

- 不读原文，只依赖场景标签数据
- 优先使用 manifest/index 减少 token 消耗
- 统计数据必须基于实际标签，不编造
- Mermaid 图表注意数据量控制（紧张度曲线可按10章采样）
- stats.yaml 保留完整数据，stats.md 做适当精简

## References

- [scenes-manifest.schema.yaml](../../../docs/schemas/scenes-manifest.schema.yaml)
- [AGENTS.md](../../AGENTS.md)
