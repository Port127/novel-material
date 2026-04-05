# Graders Index

Grader 定义目录。

## Grader 类型

|| 类型 | 用途 | 定义文件 |
||------|------|----------|
|| Deterministic | YAML 格式、ID 唯一、链接解析 | docs/evals/graders/deterministic.md |
|| LLM Rubric | 检索质量、匹配准确性 | docs/evals/graders/rubrics.md |

## 使用方式

在 task YAML 中指定 grader：

```yaml
task_id: xxx
grader: deterministic  # 或 rubric
```

## Related Docs

- [docs/evals/index.md](../docs/evals/index.md)
- [../tasks/material-skills-regression.yaml](../tasks/material-skills-regression.yaml)