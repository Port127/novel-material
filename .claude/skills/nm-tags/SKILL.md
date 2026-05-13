---
name: nm-tags
description: >-
  标签管理：统计、添加、删除、审核。仅当用户明确说出"使用 nm-tags"或"启动 nm-tags"时触发。不适用于任何隐式场景。
---

# nm-tags

标签管理系统，PostgreSQL 是唯一数据源。

## 触发约束

此 skill **仅通过显式调用触发**。

### ⛔ 不触发的场景
- 用户提到标签、分类但未提及 nm-tags
- 日常查看统计或列表
- 用户未显式引用 @nm-tags

### ✅ 触发条件
必须同时满足：
1. 用户明确说出"使用 nm-tags"或"启动 nm-tags"，或显式引用 @nm-tags
2. 用户提供了明确的标签管理需求

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