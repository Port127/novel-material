---
name: novel-characters
description: 从原文中提取人物名册、关系网和人物弧线，输出为索引加人物小传的文件夹结构
---

# 任务

生成人物体系，输出到 `characters/` 文件夹。

## 边界

用于：
- 建立人物名册
- 建立关系网
- 提取主要角色弧线

不用于：
- 把所有龙套都写成长小传
- 在本阶段穷尽事件交叉引用

## 输入

- `material_id`

## 默认执行路径

### 1. 前置检查

- `source.txt` 存在
- 有 `outline/` / `worldbuilding/` 时优先参考

### 2. 阅读策略

采用：

- outline 导航
- 分段扫描
- 滚动名册传递

### 3. 段内提取

每段关注：

- 新角色
- 弧线节点
- 关系变化
- 阵营变动

### 4. 汇总成三层输出

- `_index.yaml`：全体角色索引
- `relations.yaml`：关系网
- `profiles/`：仅主角 / 反派 / 重要配角

### 5. 角色分级

- protagonist
- antagonist
- supporting
- minor

minor 只进索引，不单开小传。

### 6. 初步交叉引用

可写 `key_events` 初稿，但完整校准留给 `refine`。

### 7. 状态写回

完成后推进到人物阶段状态。

## 输出要求

至少输出：

- 总人物数
- 主角 / 反派 / 配角 / 龙套数量
- 关系数量
- 小传文件数量

## 关键硬约束

- 长篇用滚动名册，不一次性读全文
- `key_events` ≤ 10
- minor 不生成小传
- 角色原型 / 关系类型从标签字典选取

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/role-tiering.md`
- `../../../docs/schemas/characters.schema.yaml`
- `../../../AGENTS.md`
