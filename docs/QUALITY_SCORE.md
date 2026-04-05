# Novel Material 质量评分卡

## 评分维度

|| 维度 | 权重 | 当前得分 | 目标 | 备注 |
||------|------|----------|------|------|
|| 文档覆盖 | 20% | TBD | 80% | AGENTS.md + docs/ 结构已完成 |
|| Skill 可用性 | 30% | TBD | 90% | 14 个 skills 已定义 |
|| 检索准确性 | 25% | TBD | 85% | 待 Eval 验证 |
|| 索引一致性 | 15% | TBD | 95% | 待验证 |
|| 标签规范度 | 10% | TBD | 90% | tags.yaml 已定义 |

## 总分

**当前：TBD**

**目标：85+**

## 改进计划

|| 优先级 | 改进项 | 状态 | 计划 |
||--------|--------|------|------|
|| P0 | 建立 Eval Suite | 🔴 | M3 |
|| P1 | 验证检索准确性 | 🔴 | M3 |
|| P1 | 验证索引一致性 | 🔴 | M3 |
|| P2 | 补充设计文档 | 🟡 | 进行中 |
|| P3 | 补充更多素材 | 🟡 | 持续 |

## Checklist

### 文档

- [x] AGENTS.md（≤100行）
- [x] ARCHITECTURE.md
- [x] docs/DESIGN.md
- [x] docs/PLANS.md
- [x] docs/QUALITY_SCORE.md
- [x] docs/product-specs/index.md
- [ ] docs/design-docs/core-beliefs.md（需更新）
- [x] docs/exec-plans/tech-debt-tracker.md

### Skills（活跃）

- [x] material-add
- [x] source-format
- [x] novel-outline
- [x] novel-characters
- [x] novel-tags
- [x] novel-scenes
- [x] build-index
- [x] refine
- [x] novel-stats
- [x] novel-pipeline
- [x] material-search
- [x] material-search-scene
- [x] tag-add
- [x] tag-merge

### Eval Suite

- [ ] evals/tasks/ 定义
- [ ] evals/graders/ 定义
- [ ] baseline 运行
- [ ] 评分自动化

## Last Updated

2026-04-05