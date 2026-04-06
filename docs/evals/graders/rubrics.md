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

## Unknown 逃逸口

当信息不足以做出判断时，grader 应返回 `Unknown` 而非猜测。

```yaml
escape_clause:
  condition: "场景内容缺失、标签无法解析、需求描述模糊"
  action: "返回 Unknown，不计入 pass/fail"
  report: "在结果中标记 'requires_human_review'"
```

**何时使用 Unknown：**
- 输入数据不完整（场景文件损坏）
- 需求描述歧义（多种合理解释）
- 标签字典不包含匹配值
- 检索结果格式异常

**何时不应使用 Unknown：**
- Agent 明确失败
- 格式违反契约
- 可明确判断的 pass/fail

## 人工校准流程

每个新增 rubric 或修改评分维度后，需进行人工校准：

### 校准步骤

1. **准备样本**：收集 5-10 个典型案例（pass + fail + edge）
2. **独立评分**：两位领域专家独立评分
3. **对比差异**：记录评分差异 >1 的维度
4. **调整标准**：修订 rubric 直至专家评分一致率 ≥90%
5. **记录 baseline**：写入校准结果到 `docs/evals/results/calibration/`

### 校准记录格式

```yaml
calibration:
  rubric_name: "material-search-scene"
  date: "2026-04-06"
  samples: 7
  experts: ["expert_a", "expert_b"]
  agreement_rate: 0.91
  adjusted_dimensions:
    - name: tag_match
      old_criteria: "返回场景符合标签条件"
      new_criteria: "返回场景完全符合所有显式标签条件"
```

### 校准触发条件

| 事件 | 需校准 |
|------|--------|
| 新增 rubric | 必须 |
| 修改评分维度 | 必须 |
| 新增 skill | 必须 |
| LLM 版本升级 | 建议校准 |
| 季度例行检查 | 建议 |

## 相关文档

- [../index.md](../index.md)
- [deterministic.md](deterministic.md)
- [../results/calibration/](../results/calibration/)