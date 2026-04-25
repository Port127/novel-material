# material-import 校验清单

## 至少要检查

- YAML 能否解析
- 标签是否合法
- 事件文件是否有基础必填字段
- 目录结构是否能映射到当前库

## 状态推断

- 只有原文：`raw`
- 有 outline：`outlined`
- 有 tags：`tagged`
- 有 events：`complete`
- 有 refine 痕迹或完整 stats：`refined`

## 高风险情况

- 与现有素材高度重名
- 非法标签很多
- 事件有但索引缺失
- 旧格式文件需要迁移到新结构
