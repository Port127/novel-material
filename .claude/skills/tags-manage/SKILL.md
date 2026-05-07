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
nm tags stats
```

输出示例：
```
element/common: 50 个
element/xuanhuan: 30 个
element/xianxia: 25 个
setting/cultivation: 40 个
...
```

### 列出标签

```bash
nm tags list --dimension element
```

### 添加标签

```bash
nm tags add <维度> <标签> <领域> [--group 分组]
```

示例：
```bash
nm tags add element 血脉 xuanhuan --group 设定元素
nm tags add element 血脉觉醒 xuanhuan --synonym-of 血脉
```

### 删除标签

```bash
nm tags remove <维度> <标签>
```

## 新标签审核

### 查看待审核

```bash
nm tags review
```

### 自动审批

```bash
nm tags review --auto
```

## 注意事项

1. **数据库是唯一数据源**：不要读取或编辑旧的 `data/tags.yaml`（已废弃）
2. **同义词自动映射**：`血脉觉醒` → `血脉`（synonym_of 字段）
3. **分级审核**：
   - Level 0：自由标签自动入库
   - Level 1：频率自动批（≥3 次）
   - Level 2：LLM 辅助审核
   - Level 3：人工审核（题材）