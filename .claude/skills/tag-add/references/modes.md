# tag-add 模式说明

## 模式 A：加载域包

适用于分层维度，如：

- `event_type`
- `outcome`
- `conflict`

## 模式 B：追加 custom

适用于分层维度下的用户自定义补充。

## 模式 C：扁平维度追加

适用于只有 `values` 列表的维度。

## 去重原则

- 完全重复：拒绝新增
- 高度近义：优先提示考虑 `tag-merge`
