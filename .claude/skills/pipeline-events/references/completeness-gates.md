# 完整性门控

## 输入文件

- `data/novels/{material_id}/source_entities.json`
- `data/novels/{material_id}/completeness_report.yaml`

## 决策矩阵

| 指标 | 动作 |
|------|------|
| `completeness_score < fail_threshold` | 强制阻断，脚本自动写 `status=backfill-blocked` |
| `critical_count > 0` | 即使分数达标，也会强制阻断 |
| 以上两项都不满足 | 放行到 finalize |

## 报告时要说清楚

- `completeness_score`
- `critical_count`
- 当前是否已被写成 `backfill-blocked`
- 下一步应执行 `ai-backfill`
- 补录后是否需要重建索引与重新验证
