# novel-pipeline 恢复规则

## 判断原则

1. **文件系统优先于状态字段**
2. 优先依据当前真实产物，不根据记忆推断
3. 只要下游权威产物已存在，就不要重复跑上游

## continue 恢复矩阵

| 观察到的状态 | 恢复到 |
|--------------|--------|
| `meta.yaml` 存在，`formatted != true` | `pipeline-ingest` |
| `source.txt` 与 `chapter_index.yaml` 存在，但 `outline/_index.yaml` 不存在 | `pipeline-analyze` |
| `outline/`、`worldbuilding/`、`characters/`、`tags.yaml` 已有，但 `events/` 不完整 | `pipeline-events` |
| `events/` 完整但 `events_index.yaml` 缺失 | `pipeline-events` |
| `events_index.yaml` 存在但 `source_entities.json` 或 `completeness_report.yaml` 缺失 | `pipeline-events` |
| `status=backfill-blocked` | 不进入子流水线；先执行 `ai-backfill` |
| `completeness_report.yaml` 显示未通过且 `backfill_done=false` | `pipeline-events` |
| `status=complete` 且 `pipeline.refine_batches.cleanup_done != true` | `pipeline-finalize` |
| `refined=true` 但缺少任一 `stats.*` | `pipeline-finalize` |
| refine 与 stats 都完成 | 无需继续 |

## 需要同时检查的关键文件

- `data/novels/{material_id}/meta.yaml`
- `data/novels/{material_id}/source.txt`
- `data/novels/{material_id}/chapter_index.yaml`
- `data/novels/{material_id}/outline/_index.yaml`
- `data/novels/{material_id}/worldbuilding/_index.yaml`
- `data/novels/{material_id}/characters/_index.yaml`
- `data/novels/{material_id}/tags.yaml`
- `data/novels/{material_id}/events/`
- `data/novels/{material_id}/events_manifest.yaml`
- `data/novels/{material_id}/events_index.yaml`
- `data/novels/{material_id}/source_entities.json`
- `data/novels/{material_id}/completeness_report.yaml`
- `data/novels/{material_id}/stats.yaml`
- `data/novels/{material_id}/stats.md`
- `data/novels/{material_id}/stats.html`

## 恢复时的输出重点

恢复报告至少包含：

- 当前真实阶段
- 依据的关键文件
- 发现的不一致（如 `status=tagged` 但 `events_index.yaml` 已存在）
- 本次将从哪一步继续
