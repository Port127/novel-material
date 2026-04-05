# Tech Debt Tracker

技术债务追踪。

## 当前债务

|| ID | 债务描述 | 影响 | 优先级 | 状态 |
||----|----------|------|--------|------|
|| TD-001 | 无 Eval Suite | 无法验证 skill 正确性 | P0 | 🔴 Open |
|| TD-002 | 检索准确性未验证 | 检索质量未知 | P1 | 🔴 Open |
|| TD-003 | 索引一致性未验证 | 索引可能不完整 | P1 | 🔴 Open |
|| TD-004 | 图片素材支持缺失 | 功能不完整 | P2 | 🔴 Open |

## 历史债务

| 已解决债务 | 解决方案 | 解决日期 |
|------------|----------|----------|
| 无自动化标签规范 | tag-add, tag-merge skills | 2026-04-04 |

## 债务偿还策略

- TD-001：M3 建立 Eval Suite
- TD-002, TD-003：Eval Suite 后验证
- TD-004：M4 扩展能力

## 相关文档

- [../PLANS.md](../PLANS.md)
- [../QUALITY_SCORE.md](../QUALITY_SCORE.md)