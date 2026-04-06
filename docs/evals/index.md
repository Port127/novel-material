# Novel Material Eval Suite

Eval 工程化策略。

## 目标

验证 14 个活跃 skills 的正确性与检索准确性。

## Eval 策略

### Grader 层级

| 层级 | 类型 | 用途 |
|------|------|------|
| 1 | Deterministic | YAML 格式、ID 唯一、字段完整、链接可解析 |
| 2 | LLM Rubric | 检索相关性、多维标签匹配质量 |
| 3 | Human Spot-check | 新 skill 功能验证 |

### Metrics

- `pass@k`：k 次尝试至少 1 次成功（适合检索场景）
- `pass^k`：k 次尝试全部成功（适合一致性要求场景）

## Task Categories

| 类别 | 示例任务 |
|------|----------|
| 入库 | 添加素材 → 验证 index.yaml 更新 |
| 大纲 | 生成大纲 → 验证 outline.yaml 创建 |
| 人物 | 生成人物体系 → 验证 characters.yaml 创建 |
| 场景 | 拆分场景 → 验证 scenes/*.yaml 创建 + 标签完整 |
| 检索 | 关键词检索 → 验证返回结果相关性 |
| 标签 | 标签合并 → 验证 tags.yaml 更新 |

## 目录结构

```
docs/evals/
├── index.md          # 本文件
├── graders/          # Grader 定义
│   ├── deterministic.md
│   └── rubrics.md
└── results/          # 结果存储
    └── baselines/
        └── README.md

evals/
├── tasks/            # Task YAML
├── graders/          # Grader 实现
└── results/          # 运行结果
    └── baselines/
```

## Baseline 目标

| Skill | pass@3 目标 |
|-------|-------------|
| material-add | 95% |
| source-format | 90% |
| novel-outline | 90% |
| novel-worldbuilding | 90% |
| novel-characters | 90% |
| novel-tags | 90% |
| novel-scenes | 85% |
| build-index | 95% |
| refine | 90% |
| novel-stats | 90% |
| material-search | 85% |
| material-search-scene | 80% |
| tag-add | 95% |
| tag-merge | 95% |

## Related Docs

- [../QUALITY_SCORE.md](../QUALITY_SCORE.md)
- [../PLANS.md](../PLANS.md)
- [../../AGENTS.md](../../AGENTS.md)