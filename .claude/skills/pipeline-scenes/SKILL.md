---
name: pipeline-scenes
description: 场景拆分 + 索引构建流水线（novel-scenes all → build-index）
when_to_use: 素材分析完成（status=tagged），需要拆分全书场景并建索引
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

对已分析的素材执行全书场景拆分和索引构建。

**串联 2 个子 skill：`novel-scenes`（all 模式） → `build-index`。**

这是整个流程中**最耗时**的阶段（几十到上百批次），专门设计为可跨对话恢复。

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`
2. 确认 `status` 为 `tagged` 或更高
3. 确认 `outline.yaml`、`characters.yaml` 存在（场景拆分需要参考）
4. 检查 `scenes/` 目录已处理的章节，确定恢复起点

## 恢复逻辑

| 状态 | 行为 |
|------|------|
| 无 scenes 目录或为空 | 从第 1 章开始 |
| scenes 部分完成 | 计算已覆盖章节，从未处理章节继续 |
| scenes 全部完成，无索引 | 跳过 scenes，直接执行 build-index |
| scenes + 索引都完成 | 输出"已完成" |

检测已覆盖章节的方法：
1. 扫描 `scenes/` 中所有 `ch*.yaml` 文件
2. 提取章节号，与 `chapter_index.yaml`（或 source.txt 扫描结果）对比
3. 找出缺失章节范围

## 执行步骤

### 1. 预览

```
📋 场景流水线预览

素材：{name} ({material_id})
总章节：{total_chapters}

场景拆分状态：
  已完成：{done_chapters}/{total_chapters} 章（{done_scenes} 个场景）
  待处理：第 {start}-{end} 章
  预计批次：{batch_count} 批（每批 {batch_size} 章）

将执行：
  1. novel-scenes (all)  → 拆分剩余章节场景
  2. build-index         → 构建倒排索引 + 场景清单

⚠️ 场景拆分将自动循环分批执行
⚠️ 每 30 批建议开新对话恢复，避免上下文膨胀

确认开始？(yes/no)
```

### 2. 执行 novel-scenes（all 模式）

读取 `novel-scenes/SKILL.md` 并按其指令执行，关键参数：

- 模式：`all`（自动循环分批）
- 起始章节：从未覆盖的第一章开始
- 质量审计：每批完成后运行 `quality_audit.py --batch {本批范围}`

**⚠️ 关键：`--batch` 参数只传本批范围（如 `421-450`），不传累积范围（如 `1-450`）。**

每批完成后输出进度：

```
[批次 {n}/{total}] 第 {start}-{end} 章完成，{scene_count} 个场景 ✅ (diversity={diversity})
```

### 3. 对话分段策略

场景拆分是长耗时任务，context window 会逐步膨胀。**必须**执行以下控制：

- **每处理 30 批**：输出分段提醒
  ```
  ⏸️ 已完成 30 批，建议开新对话恢复：
     /pipeline-scenes {material_id}
  ```
- **批间不累积上下文**：每批只读当前批的原文，上一批的输出不带入下一批
- **进度持久化**：每批完成后立即更新 `meta.yaml`，即使对话中断也不丢失进度

### 4. 执行 build-index

全书场景完成后，读取 `build-index/SKILL.md` 并执行：

- 构建 `scenes_index.yaml`（倒排索引）
- 构建 `scenes_manifest.yaml`（场景清单）
- 构建 SQLite 索引
- 聚合全局人物/剧情索引

### 5. 更新状态

```yaml
status: complete
pipeline:
  current_stage: complete
  stages_completed: [..., scenes, build-index]
  scenes_processed: [1-{total_chapters}]
  scenes_in_progress: false
  index_built: true
  index_at: {timestamp}
```

### 6. 输出报告

```
✅ 场景拆分 + 索引构建完成

📚 素材：{name}
📖 总章节：{total_chapters}章
🎬 场景总数：{total_scenes}个
📊 覆盖率：100%

📄 倒排索引：scenes_index.yaml
📄 场景清单：scenes_manifest.yaml
📄 SQLite：data/material.db

后续操作：
  /pipeline-finalize {material_id}    # 精调 + 统计报告
  /novel-pipeline full {material_id}  # 继续完整流程
```

## 硬约束

- MUST 先预览再执行
- MUST `--batch` 参数只传本批新增范围，不传累积范围
- MUST 每批完成后立即写入文件 + 更新 meta.yaml
- MUST 每 30 批输出分段提醒
- MUST 批间不累积上下文（不把上一批场景数据带入下一批）
- MUST scenes 全部完成后才执行 build-index
- NEVER 在一个对话内强行跑完超长小说的全部场景（适时提醒分段）

## References

- [novel-scenes/SKILL.md](../novel-scenes/SKILL.md)
- [build-index/SKILL.md](../build-index/SKILL.md)
- [AGENTS.md](../../../AGENTS.md)
