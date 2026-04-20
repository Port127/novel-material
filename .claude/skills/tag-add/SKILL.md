---
name: tag-add
description: 向标签字典新增标签值（支持加载主题域包和自定义扩展）
when_to_use: 场景打标签时发现现有标签值不够用
argument-hint: "[维度] [主题域 | custom | 新值]"
arguments: dimension, target
---

# 任务

向 `data/tags.yaml` 的指定维度新增标签值。支持三种模式：

| 调用方式 | 行为 |
|----------|------|
| `/tag-add {维度} {主题域}` | 加载预定义的主题域包（如 romance、politics） |
| `/tag-add {维度} custom {值}` | 向自定义域添加用户自定义值 |
| `/tag-add {维度} {值}` | 向核心层直接添加值（仅适用于无分层维度） |

## 分层架构说明

tags.yaml 采用三层结构：

```
├── 核心层（core）：必选，通用维度
├── 扩展层（domains）：可选，按主题域包组织
│   ├── romance（爱情）
│   ├── politics（权谋）
│   ├── martial（武侠）
│   ├── mystery（悬疑）
│   ├── family（家国）
│   └── custom（自定义）
└── 自定义层：用户扩展
```

**分层维度**（有 core + domains 结构）：
- `event_type`
- `outcome`
- `conflict`

**扁平维度**（只有 values 列表）：
- `scene_type`, `emotion`, `technique`, `relationship` 等其他维度

## 前置检查

1. 读取 `data/tags.yaml`
2. 确认维度存在
3. 判断维度是否分层（有 core 字段）

## 执行步骤

### 模式 A：加载主题域包

**调用**：`/tag-add event_type romance`

#### A1. 验证维度分层

确认维度有 `core` 和 `domains` 字段。若为扁平维度，提示用户直接用模式 C。

#### A2. 验证主题域存在

确认 `domains` 下有对应主题域（romance/politics/martial/mystery/family）。

若不存在，提示用户可用主题域列表。

#### A3. 加载域包

将主题域的 `values` 合入核心层（或标记为已加载）。

#### A4. 输出

```
✅ 主题域包已加载

📂 维度：event_type
📦 域包：romance（爱情相关事件）
🏷️ 新增值（10个）：
   - 恋爱萌芽
   - 告白事件
   - 恋爱升温
   - 恋爱危机
   - ...

📊 event_type 现有 {count} 个可用值
   - 核心层：{core_count}
   - romance 域：{domain_count}
```

---

### 模式 B：添加自定义值

**调用**：`/tag-add event_type custom 恋爱求婚`

#### B1. 验证维度分层

确认维度有 `core` 和 `domains` 字段。

#### B2. 检查重复

确认值不在 `core` 和所有 `domains.values` 中。

#### B3. 追加到 custom 域

在 `domains.custom.values` 列表末尾追加新值。

#### B4. 输出

```
✅ 自定义值已新增

📂 维度：event_type
📦 域：custom
🏷️ 新值：恋爱求婚
📊 custom 域现有 {count} 个值
```

---

### 模式 C：向扁平维度添加值

**调用**：`/tag-add emotion 满足`

#### C1. 验证维度扁平

确认维度只有 `values` 字段，无 `core`。

#### C2. 检查重复

确认值不在 `values` 列表中。

#### C3. 追加值

在 `values` 列表末尾追加新值。

#### C4. 输出

```
✅ 标签已新增

📂 维度：emotion（情绪基调）
🏷️ 新值：满足
📊 该维度现有 {count} 个值
```

---

## 可用主题域列表

| 主题域 | 适用维度 | 说明 |
|--------|----------|------|
| `romance` | event_type, outcome, conflict | 爱情/恋爱相关 |
| `politics` | event_type, outcome, conflict | 权谋/政治相关 |
| `martial` | event_type, outcome, conflict | 武侠/江湖相关 |
| `mystery` | event_type, outcome, conflict | 悬疑/推理相关 |
| `family` | event_type, outcome, conflict | 家庭/家国相关 |
| `custom` | 所有分层维度 | 用户自定义扩展 |

## 注意事项

- 值应简洁（2-6字为佳）
- 避免同义重复（如"争斗"和"对决"）
- 如有近义值，建议先 `/tag-merge` 确认
- 分层维度优先用主题域包，而非直接向 core 添加
- 新值立即可用于后续场景标签

## 示例

```
# 加载爱情域包到 event_type
/tag-add event_type romance

# 加载权谋域包到 conflict
/tag-add conflict politics

# 自定义添加恋爱求婚到 event_type
/tag-add event_type custom 恋爱求婚

# 向扁平维度 emotion 添加新值
/tag-add emotion 满足
```

## References

- [tags.yaml](../../../data/tags.yaml)
- [tag-merge/SKILL.md](../tag-merge/SKILL.md)