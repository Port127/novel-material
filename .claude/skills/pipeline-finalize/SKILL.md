---
name: pipeline-finalize
description: 精调 + 统计报告流水线（refine → novel-stats）
when_to_use: 场景拆分和索引都完成后（status=complete），生成精调产出和统计报告
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

在场景数据齐备后，精调早期产出物并生成全书统计报告。

**串联 2 个子 skill：`refine` → `novel-stats`。**

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`
2. 确认 `status` 为 `complete` 或更高
3. 确认 `scenes_index.yaml` 或 `scenes_manifest.yaml` 存在
4. 确认 `outline.yaml`、`characters.yaml`、`tags.yaml` 存在

## 恢复逻辑

| 状态 | 行为 |
|------|------|
| refined=false, stats_generated=false | 执行 refine → novel-stats |
| refined=true, stats_generated=false | 跳过 refine，执行 novel-stats |
| 均已完成 | 输出"已完成" |

## 执行步骤

### 1. 预览

```
📋 精调+统计流程预览

素材：{name} ({material_id})
状态：{status}
场景数：{total_scenes}

将执行：
  1. refine       → 精调大纲/世界观/人物/标签（基于场景数据反哺）
  2. novel-stats  → 生成统计报告 + 交互图表 + 关系图谱

{如有跳过} ⏭️ 已完成阶段将跳过：{列表}

确认开始？(yes/no)
```

### 2. 执行 refine

读取 `refine/SKILL.md` 并执行。主要产出：

- 伏笔网络补充
- 节奏曲线补充
- 人物弧线细化
- 关系演变时间线
- 世界观信息补充
- 小说级标签校准

### 3. 执行 novel-stats

读取 `novel-stats/SKILL.md` 并执行。主要产出：

- `stats.yaml`（原始统计数据）
- `stats.md`（Mermaid 可视化报告）
- `stats.html`（ECharts 交互报告 + 关系图谱）

### 4. 更新状态

```yaml
status: refined
pipeline:
  stages_completed: [..., refine, novel-stats]
  refined: true
  refined_at: {timestamp}
  stats_generated: true
  stats_at: {timestamp}
```

### 5. 输出最终报告

```
✅ 精调 + 统计报告完成

📚 素材：{name}

精调结果：
  📖 outline.yaml — 伏笔 +{n}，节奏曲线 +{n} 点
  👥 characters.yaml — {n} 角色弧线细化，{n} 关系演变
  🗺️ worldbuilding.yaml — {n} 处补充
  🏷️ tags.yaml — {n} 维度校准

统计报告：
  📊 stats.yaml / stats.md / stats.html
  🎬 场景总数：{total_scenes}
  📈 转折点：{turning_count}
  🔮 伏笔：{plant}/{payoff}/{unresolved}

📁 全部完成！素材状态：refined

后续操作：
  /material-search [关键词]             # 关键词检索
  /material-search-scene [需求描述]     # 多维标签检索
  /material-search-context [写作上下文] # 写作场景检索
```

## 硬约束

- MUST 先预览再执行
- MUST refine 只读场景数据，不读原文
- MUST novel-stats 只读场景数据 + manifest/index，不读原文
- MUST 精调前备份待修改文件（.bak）
- MUST 支持从中断点恢复
- NEVER 编造统计数据（无信号写 TBD）

## References

- [refine/SKILL.md](../refine/SKILL.md)
- [novel-stats/SKILL.md](../novel-stats/SKILL.md)
- [AGENTS.md](../../../AGENTS.md)
