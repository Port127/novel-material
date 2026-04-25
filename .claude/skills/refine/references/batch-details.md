# refine 批次细则

## batch-1：统计合并

来源：`refine_input.json`

主要写入：

- `characters/_index.yaml`
- `outline/pacing_curve.yaml`
- `worldbuilding/` 相关统计
- `tags.yaml` 的主导分布

## batch-2：钩子验证

每次只处理少量钩子，重点：

- planted / harvested 是否成立
- 置信度是否应调整
- 无证据的低置信度钩子应删除或保留为 pending

主要更新：

- `outline/hooks_network.yaml`

## batch-2b：交汇验证

重点：

- `events/cross_thread_events.yaml`
- `outline/subplots.yaml`
- `outline/plotlines.yaml`

校准：

- 交汇类型
- anchor chapters
- 无效交汇删除

## batch-3：人物

重点：

- `characters/_index.yaml`
- `characters/relations.yaml`
- `characters/profiles/*.yaml`

检查：

- `key_events` 是否有效
- 升格 / 降格是否有事件依据

## batch-4：关系

逐对验证关系演变，更新：

- `characters/relations.yaml`

## batch-5：世界观

重点：

- `_index.yaml`
- geography / factions / lore

根据实际数量决定 `merge` 或 `split`。

## batch-6：清理与收口

必须完成：

- 删除无效引用
- 校准 `tags.yaml`
- 刷新 `refine_hash`
- 写最终状态
