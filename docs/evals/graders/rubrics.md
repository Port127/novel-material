# LLM Rubric Graders

LLM 评分规则。

## 检索相关性评分

### material-search

```yaml
rubric:
  dimensions:
    relevance:  # 返回结果与关键词相关
      weight: 0.5
      criteria:
        - 返回素材包含关键词或相关概念
        - 返回素材数量合理（3-10个）
        - 排序符合相关性逻辑
    completeness:  # 覆盖度
      weight: 0.3
      criteria:
        - 包含已知匹配素材
        - 无明显遗漏
    format:  # 输出格式
      weight: 0.2
      criteria:
        - 输出格式符合 skill 定义
        - 包含必要字段
```

### material-search-scene

```yaml
rubric:
  dimensions:
    tag_match:  # 标签匹配正确性
      weight: 0.4
      criteria:
        - 返回场景符合标签条件
        - 多维标签识别准确
    content_quality:  # 内容质量
      weight: 0.3
      criteria:
        - 返回场景符合需求描述
        - 场景内容完整可理解
    diversity:  # 多样性
      weight: 0.2
      criteria:
        - 返回场景来自不同素材
        - 提供多种风格选择
    format:
      weight: 0.1
```

## 生成质量评分

### novel-outline

```yaml
rubric:
  dimensions:
    structure:  # 结构完整
      weight: 0.4
      criteria:
        - 包含三幕结构划分
        - 关键节点定义清晰
    pacing:  # 节奏分析
      weight: 0.3
      criteria:
        - 节奏标注准确
        - 高潮低谷识别正确
    foreshadowing:  # 伏笔追踪
      weight: 0.2
      criteria:
        - 伏笔埋设位置标注
        - 伏笔揭示位置标注
    format:
      weight: 0.1
```

### novel-characters

```yaml
rubric:
  dimensions:
    roster:  # 名册完整
      weight: 0.4
      criteria:
        - 主要人物均有记录
        - 人物基本信息完整
    relationships:  # 关系网
      weight: 0.3
      criteria:
        - 人物关系标注准确
        - 关系类型分类合理
    arcs:  # 人物弧线
      weight: 0.2
      criteria:
        - 主要人物弧线标注
        - 弧线变化节点识别
    format:
      weight: 0.1
```

### novel-scenes

```yaml
rubric:
  dimensions:
    segmentation:  # 场景拆分
      weight: 0.3
      criteria:
        - 场景边界识别准确
        - 场景粒度合理
    tagging:  # 标签质量
      weight: 0.4
      criteria:
        - 6层标签覆盖完整
        - 标签值选择准确
    content:  # 内容提取
      weight: 0.2
      criteria:
        - 场景摘要准确
        - 关键信息保留
    format:
      weight: 0.1
```

## 评分标准

|| 分数 | 含义 |
||------|------|
|| 5 | 完美符合所有标准 |
|| 4 | 符合大部分标准，小瑕疵 |
|| 3 | 基本符合，有明显改进空间 |
|| 2 | 部分符合，需改进 |
|| 1 | 不符合或失败 |

Pass 阈值：平均分 ≥ 4

## 相关文档

- [../index.md](../index.md)
- [deterministic.md](deterministic.md)