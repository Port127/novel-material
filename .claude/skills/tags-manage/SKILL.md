---
name: tags-manage
description: 标签管理：查看统计、导出视图、添加/删除标签、审核新标签候选。当用户需要管理标签字典时使用。
---

# tags-manage

标签管理系统，PostgreSQL 是唯一数据源。

## 标签体系

| 维度 | 说明 | 领域 |
|------|------|------|
| element | 小说元素 | common/xuanhuan/xianxia/dushi/kehuan/qihuan/lingyi |
| setting | 世界观体系 | cultivation/magic/modern/kehuan/wuxia |
| style | 叙事风格 | common（全领域通用） |
| structure | 叙事结构 | common（全领域通用） |

## 常用命令

### 查看统计

```bash
python scripts/tags/manage.py stats
# 或
make tags-stats
```

输出示例：
```
element/common: 50 个
element/xuanhuan: 30 个
element/xianxia: 25 个
setting/cultivation: 40 个
...
```

### 导出 YAML 视图

```bash
python scripts/tags/manage.py export
# 或
make tags-export
```

输出：`data/tags_view.yaml`（人读视图，不参与代码逻辑）

### 添加标签

```bash
python scripts/tags/manage.py add <维度> <标签> <领域> [--group 分组]
```

示例：
```bash
python scripts/tags/manage.py add element 血脉 xuanhuan --group 设定元素
python scripts/tags/manage.py add element 血脉觉醒 xuanhuan --synonym-of 血脉
```

### 删除标签

```bash
python scripts/tags/manage.py remove <维度> <标签>
```

### 移动标签领域

```bash
python scripts/tags/manage.py move <维度> <标签> <新领域>
```

### 列出标签

```bash
python scripts/tags/manage.py list-tags --dimension element
```

## 新标签审核

### 查看待审核

```bash
python scripts/tags/review.py list
# 或
make tags-review
```

### 批准标签

```bash
python scripts/tags/review.py approve <候选ID> --domain <领域>
```

示例：
```bash
python scripts/tags/review.py approve 1 --domain xuanhuan --group 设定元素
```

### 拒绝标签

```bash
python scripts/tags/review.py reject <候选ID>
```

### 批量处理

```bash
# 频率自动批（element/style 出现 ≥3 次自动入库）
python scripts/tags/scheduled.py auto-approve

# LLM 辅助审核（setting/structure）
python scripts/tags/scheduled.py llm-review
```

## 校验标签

```bash
python scripts/tags/validate.py element 血脉
```

返回：`血脉`（合法）或 `None`（非法）

批量校验：
```python
from scripts.tags.validate import validate_tags_batch
valid, invalid = validate_tags_batch('element', ['血脉', '不存在的'])
```

## 注意事项

1. **数据库是唯一数据源**：不要读取或编辑 `data/tags.yaml`（已废弃）
2. **YAML 仅为人读视图**：`data/tags_view.yaml` 不参与代码逻辑
3. **同义词自动映射**：`血脉觉醒` → `血脉`（synonym_of 字段）
4. **分级审核**：
   - Level 0：自由标签自动入库
   - Level 1：频率自动批（≥3 次）
   - Level 2：LLM 辅助审核
   - Level 3：人工审核（题材）