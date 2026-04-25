# pipeline-events 恢复规则

## 恢复优先级

1. `events/` 实际覆盖情况
2. `events_manifest.yaml` / `events_index.yaml`
3. `source_entities.json`
4. `completeness_report.yaml`
5. `meta.yaml`

## 常见恢复点

| 检测结果 | 说明 | 恢复动作 |
|----------|------|----------|
| `events/` 空 | 事件未开始 | 从 `novel-events all` 开始 |
| `events/` 非空但覆盖不全 | 拆分中断 | 从未覆盖章节继续 |
| 事件全有，索引缺失 | `build-index` 未完成 | 直接 `build-index` |
| 索引有，实体清单缺失 | 完整性验证未开始 | 跑 `extract_source_entities.py` |
| 实体清单有，完整性报告缺失 | 验证未完成 | 跑 `validate_completeness.py` |
| 完整性未通过，`backfill_done != true` | 需要补录 | 跑 `ai-backfill` |

## 判断事件是否“全部完成”

至少满足：

1. 主线章节无连续缺口超过 3
2. `quality_audit.py {material_id}` 通过
3. `events/` 中章节覆盖与 `chapter_index.yaml` 对齐

不要仅凭文件数量判断“全书已拆完”。
