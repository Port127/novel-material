# evidence 规则

## 每批完成时必须写什么

### 通用字段

```yaml
pipeline:
  refine_batches:
    batch_outputs:
      batch_x:
        completed_at: "2026-04-25T12:00:00Z"
        evidence_list: [...]
```

## 可以接受的 evidence

- `hooks_verified_list`
- `profiles_updated`
- `relations_verified_list`
- `worldbuilding_updated`
- `cleanup_items`
- `stats_updated`

## 不允许的情况

- `completed_at` 缺失
- evidence list 为空却把状态写成 `true`
- 写了并不存在的 hook / relation / profile / file

## 输出时要说明

- 哪些 evidence 是新增
- 哪些是修正
- 哪些是删除
