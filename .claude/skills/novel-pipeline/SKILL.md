---
name: novel-pipeline
description: 一键触发素材处理流程，支持阶段门禁、状态追踪、中断恢复
when_to_use: 用户想要一键执行完整流程、从中断点恢复、或批量触发多个 skill
argument-hint: "[模式] [参数]"
arguments: mode, params
---

# 任务

一键触发素材处理流程，串联 `material-add → source-format → novel-outline → novel-characters → novel-tags → novel-scenes → build-index → refine → novel-stats`。

## 角色定位

- 流程编排器：根据模式参数选择执行路径
- 阶段门控：preview → confirm → execute → verify → report
- 状态追踪：支持中断恢复

**不直接执行文件操作，通过调用子 skill 完成。**

## 流程路由

| 模式 | 触发词 | 流程 | 参数 |
|------|--------|------|------|
| `full` | 一键处理、完整流程、全自动 | material-add → source-format → outline → characters → tags → scenes → build-index → refine → novel-stats | `[路径]` |
| `quick` | 快速处理、仅骨架 | material-add → source-format → outline → characters | `[路径]` |
| `continue` | 继续、恢复、接着处理 | 从上次中断点恢复 | `[material_id]` |
| `stage` | 大纲、人物、标签、场景、格式化、索引、精调、统计 | 仅执行指定阶段 | `[material_id] [阶段名]` |

**MUST 先输出「流程预览 + 确认请求」，仅在用户明确确认后开始执行。**

## 状态机

```
INIT → ROUTE_IDENTIFIED → PREVIEW_READY → AWAIT_CONFIRM → EXECUTING → STAGE_DONE → NEXT_STAGE → COMPLETE
                                                                                                  ↘ FAILED
                                                                       ↘ PAUSED
```

## 处理阶段定义

| 阶段序号 | 阶段名 | 子 Skill | 输入 | 输出 |
|----------|--------|----------|------|------|
| 1 | `material-add` | material-add | 文件路径 | material_id |
| 2 | `source-format` | source-format | material_id | 清洗后 source.txt + format_report.yaml |
| 3 | `outline` | novel-outline | material_id | outline.yaml |
| 4 | `characters` | novel-characters | material_id | characters.yaml |
| 5 | `tags` | novel-tags | material_id | tags.yaml |
| 6 | `scenes` | novel-scenes | material_id + 章节范围 | scenes/*.yaml |
| 7 | `build-index` | build-index | material_id | scenes_index.yaml + scenes_manifest.yaml |
| 8 | `refine` | refine | material_id | 精调后的 outline/characters/tags |
| 9 | `novel-stats` | novel-stats | material_id | stats.yaml + stats.md |

## 执行步骤

### 1. 识别意图

根据用户输入判断模式：
- 含文件路径 + 含"一键/完整/全自动" → `full`
- 含文件路径 + 含"快速/骨架" → `quick`
- 含 material_id + 含"继续/恢复" → `continue`
- 含 material_id + 含"大纲/人物/标签/场景" → `stage`

### 2. 生成预览

根据模式生成执行计划预览：

```
📋 流程预览

模式：{mode}
素材：{路径 或 material_id}

将执行以下阶段：
  1. material-add     → 入库（状态：raw）
  2. source-format    → 格式清洗（状态：raw）
  3. novel-outline    → 生成大纲（状态：outlined）
  4. novel-characters → 生成人物体系（状态：outlined）
  5. novel-tags       → 生成小说标签（状态：tagged）
  6. novel-scenes     → 拆分场景（状态：complete）
  7. build-index      → 构建索引（状态：complete）
  8. refine           → 精调大纲/人物/标签（状态：refined）
  9. novel-stats      → 生成统计报告（状态：refined）

预计耗时：{估算}
⚠️ 场景拆分将分批执行（每批 5 章）

确认开始执行？(yes/no)
```

### 3. 等待确认

输出预览后等待用户明确回复 `yes` 或 `no`：
- `yes` → 进入 `EXECUTING`
- `no` → 进入 `PAUSED`，询问是否调整参数

### 4. 执行阶段

按序调用子 skill，每个阶段：

1. 调用对应子 skill（读取其 SKILL.md 并执行）
2. 等待子 skill 完成
3. 收集输出结果
4. 根据结果决定下一步：
   - 成功 → 进入下一阶段
   - 需确认 → 停留，请求用户确认
   - 阻塞 → 停止，回显阻塞原因
   - 失败 → 进入 FAILED，请求用户决定

### 5. 场景分批处理

`novel-scenes` 阶段需分批执行：
- 首批：处理前 5 章
- 每批完成后询问是否继续下一批
- 用户可随时暂停，状态保存到 `meta.yaml`

### 6. 生成报告

所有阶段完成后输出最终报告：

```
✅ 处理流程完成

📚 紎材 ID：{material_id}
📁 文件夹：data/novels/{material_id}/

生成文件：
  - meta.yaml              (元数据)
  - source.txt             (清洗后原文)
  - source.raw.txt         (原始备份)
  - format_report.yaml     (格式清洗报告)
  - outline.yaml           (故事大纲，已精调)
  - characters.yaml        (人物体系，已精调)
  - tags.yaml              (小说标签，已精调)
  - scenes/*.yaml          ({N} 个场景)
  - scenes_index.yaml      (倒排索引)
  - scenes_manifest.yaml   (场景清单)
  - stats.yaml             (统计数据)
  - stats.md               (可视化报告)

状态：refined

后续操作：
  /material-search [关键词]       # 关键词检索
  /material-search-scene [需求]   # 多维标签检索
```

## 中断恢复

当用户使用 `/novel-pipeline continue {material_id}`：

1. 读取 `data/novels/{material_id}/meta.yaml`
2. 检查 `status` 和 `pipeline` 字段：
   - `raw` + 未格式化 → 从 `source-format` 阶段恢复
   - `raw` + 已格式化 → 从 `outline` 阶段恢复
   - `outlined` → 从 `tags` 阶段恢复
   - `tagged` → 从 `scenes` 阶段恢复（检查已处理章节）
   - `complete` + 未构建索引 → 从 `build-index` 阶段恢复
   - `complete` + 未精调 → 从 `refine` 阶段恢复
   - `complete`/`refined` + 未统计 → 从 `novel-stats` 阶段恢复
3. 显示恢复预览，等待确认后继续

## 状态追踪

状态保存在 `meta.yaml` 的 `pipeline` 字段：

```yaml
pipeline:
  mode: full
  current_stage: scenes
  stages_completed: [material-add, source-format, outline, characters, tags]
  scenes_processed: [1-5, 6-10]
  formatted: true
  index_built: false
  refined: false
  stats_generated: false
  paused_at: "2026-04-05T10:30:00Z"
```

## 硬约束

- MUST 先 preview 再执行
- MUST 写操作前用户确认
- MUST 每阶段记录状态
- MUST 场景拆分分批执行
- MUST 支持中断恢复
- NEVER 跳过阶段门禁
- NEVER 一次处理全书场景

## 示例

### 一键完整处理

```
用户: /novel-pipeline full /path/to/novel.txt

novel-pipeline:
  📋 流程预览
  模式：full
  素材：/path/to/novel.txt
  
  将执行 5 个阶段...
  
  确认开始执行？

用户: yes

novel-pipeline:
  [1/9] 执行 material-add...
  ✅ 入库完成，ID: nm_novel_20260405_x1y2
  
  [2/9] 执行 source-format...
  ✅ 格式清洗完成（修复 87 处引号，标准化 1070 个章节名）
  
  [3/9] 执行 novel-outline...
  ✅ 大纲已生成
  
  [4/9] 执行 novel-characters...
  ✅ 人物体系已生成
  
  [5/9] 执行 novel-tags...
  ✅ 小说标签已生成
  
  [6/9] 执行 novel-scenes (第 1-5 章)...
  ✅ 场景拆分完成（12 个场景）
  
  继续处理第 6-10 章？

用户: yes

  ... (场景分批处理直到全部完成) ...

novel-pipeline:
  ✅ 全部场景拆分完成（907 个场景）
  
  [7/9] 执行 build-index...
  ✅ 索引构建完成（倒排索引 + 场景清单）
  
  [8/9] 执行 refine...
  ✅ 精调完成（伏笔 +15、节奏曲线 +1070 点、弧线细化 8 角色）
  
  [9/9] 执行 novel-stats...
  ✅ 统计报告已生成
  
  ✅ 处理流程全部完成
```

## References

- [AGENTS.md](../../AGENTS.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)