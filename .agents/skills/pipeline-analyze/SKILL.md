# pipeline-analyze

分析流水线：大纲 + 世界观 + 人物 + 标签 + 章级分析。

## 用法

```bash
python scripts/pipeline.py analyze <material_id>
```

## 流程

1. 章级分析（LLM 为每章生成摘要+出场人物+功能标签）
2. 大纲生成（structure.yaml, hooks_network.yaml）
3. 世界观提取（worldbuilding/）
4. 人物提取（characters/）
5. 标签生成（tags.yaml）
6. 质量校验
7. 同步数据库

## 输出状态

- meta.yaml 中 `status: analyzed`

## 质量校验

运行后执行 `python scripts/utils/quality_check.py <material_id>` 校验结果。
