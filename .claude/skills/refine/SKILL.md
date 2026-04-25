---
name: refine
description: 在事件完成后用事件数据反哺 outline、characters、worldbuilding 与 tags；只做基于证据的精调与重构
---

# 任务

基于事件数据精调早期产出物：

- `outline/`
- `characters/`
- `worldbuilding/`
- `tags.yaml`

**原则：调整而非增量。** 可以补充、校准、合并、拆分、删除、重构，但所有动作都必须有事件证据。

## 边界

用于：
- events、index、完整性验证都完成后的结构性精修
- 用 `refine_input.json` 降低上下文成本

不用于：
- 直接读取原文
- 绕过完整性门控
- 无证据地补人物 / 补世界观 / 补钩子

## 前置检查

开始前必须确认：

1. `events/` 存在且非空
2. `completeness_report.yaml` 允许进入 refine
3. `outline/`、`characters/`、`worldbuilding/`、`tags.yaml` 已存在
4. 如无 `refine_input.json`，先运行：

```bash
python scripts/core/extract_refine_data.py {material_id}
```

## 默认执行路径

### 0. 准备阶段

#### 0a. 变化检测

运行：

```bash
python scripts/core/extract_refine_data.py {material_id} --no-update-meta --output /tmp/current_hash.json
```

比较当前 `events_hash` 与 `meta.yaml` 中的 `refine_hash`：

- 相同：直接报告“事件未变化，无需重复 refine”
- 不同：继续执行

#### 0b. 带时间戳备份

修改前创建时间戳备份，不清理旧备份：

- `outline.bak.{timestamp}/`
- `characters.bak.{timestamp}/`
- `worldbuilding.bak.{timestamp}/`
- `tags.yaml.bak.{timestamp}`

### 1. 分批精调

按以下顺序推进：

| 批次 | 目标 |
|------|------|
| batch-1 | 合并统计数据 |
| batch-2 | 验证钩子并建立铆合链 |
| batch-2b | 验证跨线索交汇 |
| batch-3 | 精调人物弧线、小传、关键事件 |
| batch-4 | 验证关系演变 |
| batch-5 | 精调世界观与粒度结构 |
| batch-6 | 清理无效引用、校准 tags、更新 refine_hash |

### 2. 证据先行

每个批次完成时必须同时写入：

- `completed_at`
- 本批实际修改对象列表
- 对应 evidence list

**禁止空列表标记完成。**

### 3. 中断恢复

如果中断：

- 读取 `meta.yaml` 的 `pipeline.refine_batches.current_batch`
- 从当前批次继续
- 不要求用户“继续下一批”；只要本轮还能做，就继续做

### 4. 完成收口

最后必须：

1. 清理无效事件引用
2. 校准 `tags.yaml`
3. 刷新 `refine_hash`
4. 写回 `pipeline.refined=true`

## 操作类型

允许的精调动作：

- `enrich`
- `adjust`
- `merge`
- `split`
- `delete`
- `restructure`

所有操作都要在输出里汇总统计。

## 关键硬约束

- 不读原文，只读事件 YAML / manifest / `refine_input.json`
- `key_events` 只保留关键节点，≤ 10
- 无证据不新增，无依据不删除
- 指向不存在事件的引用必须清理
- 每批状态更新必须带证据列表
- 不能通过手工改状态绕过未完成批次

## 输出要求

至少汇报：

- 从哪一批开始 / 恢复
- 各批修改了哪些文件
- 证据列表写了什么
- `refine_hash` 是否更新
- 还剩哪一批未完成（如有）

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/batch-details.md`
- `references/evidence-rules.md`
- `../../../docs/schemas/outline.schema.yaml`
- `../../../docs/schemas/worldbuilding.schema.yaml`
- `../../../docs/schemas/characters.schema.yaml`
- `../../../docs/schemas/novel-tags.schema.yaml`
- `../../../AGENTS.md`
