---
name: pipeline-ingest
description: 处理新素材入库与格式清洗；串联 material-add 和 source-format，产出可分析的干净 source.txt
---

# 任务

把一个新素材安全入库，并完成格式清洗，产出：

- `meta.yaml`
- `source.txt`
- `chapter_index.yaml`
- `format_report.yaml`

## 适用边界

用于：
- 新文件首次入库
- full pipeline 的第一阶段

不用于：
- 跳过 `source-format`
- 直接替代 `material-add` 或 `source-format`

## 输入

- 文件路径

## 默认执行路径

### 1. 前置检查

- 文件路径存在
- `data/index.yaml` 可读取
- 如命中疑似重复，交给 `material-add` 自己处理冲突分支

### 2. 执行顺序

严格按顺序调用：

1. `material-add`
2. `source-format`

`material-add` 未成功前，禁止进入 `source-format`。

### 3. 质量检查

完成后运行：

```bash
python scripts/core/validate_yaml.py meta {material_id}
```

同时检查：

- `format_report.yaml` 是否生成
- `chapter_index.yaml` 是否生成
- 章节连续性是否存在缺口

如果章节缺失属于明确异常，报告风险并停止后续阶段。

### 4. 状态写回

在 `meta.yaml` 中至少写入：

- `pipeline.mode = ingest`
- `stages_completed = [material-add, source-format]`
- `formatted = true`

## 输出要求

至少输出：

- `material_id`
- 入库后的目录
- 清洗结果摘要
- 是否存在章节异常
- 下一步建议：`pipeline-analyze`

## 关键硬约束

- 不跳过 `source-format`
- 不在本 skill 内重复展开子 skill 细节
- 非冲突场景下不做额外 yes/no 确认

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `../material-add/SKILL.md`
- `../source-format/SKILL.md`
- `../../../AGENTS.md`
