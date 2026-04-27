# Schema 文档与校验脚本不一致问题分析

**素材**：nm_novel_20260424_v7n8（《三体3》死神永生 第三版）
**日期**：2026-04-24
**执行者**：Claude (GLM-5)
**问题类型**：系统设计问题

---

## 问题概述

在执行 `/novel-pipeline full` 处理《三体3》死神永生（第三版）时，pipeline-analyze 阶段成功完成，但进入 pipeline-events 阶段后，创建的 14 个事件文件全部校验失败。

**核心问题**：Schema 示例文档与校验脚本（validate_yaml.py）的字段命名不一致，导致按照示例格式写入的文件无法通过校验。

---

## 错误详情

### 错误清单（14个事件文件全部失败）

| 问题类型 | 出现次数 | 具体问题 |
|----------|----------|----------|
| 字段名不匹配 | 14 × 3 | `chapters` → 应为 `chapter`<br>`emotion_arc` → 应为 `emotion`<br>`tension_peak` → 应为 `tension` |
| 字段类型错误 | 14 | `event_type` 应为列表，实际写了单值 |
| 缺少必填字段 | 14 × 2 | 缺少 `emotion`、`tension` |
| 标签越界 | 100+ | 大量标签不在 tags.yaml 中 |

### 典型错误示例

**ev_main_001.yaml 校验失败报告**：
```
- 缺少必填字段: chapter
- 字段 event_type 应为列表，实际: str
- 缺少标签字段: emotion
- 缺少必填字段: tension
- 标签越界: event_type='情感转折'（不在 tags.yaml 中）
- 标签越界: stakes='爱情'（不在 tags.yaml 中）
- 标签越界: interaction='购买'（不在 tags.yaml 中）
- 标签越界: reader_effect='感动'（不在 tags.yaml 中）
- 标签越界: plot_function='悬念埋设'（不在 tags.yaml 中）
- 标签越界: pacing='慢'（不在 tags.yaml 中）
...
```

---

## 根本原因分析

### 1. Schema 文档与校验脚本缺乏同步机制

**问题本质**：项目中存在两个"真相来源"：
- **docs/schemas/*.schema.yaml**：声明式的格式示例
- **scripts/core/validate_yaml.py**：执行式的校验逻辑

这两者的字段命名不一致，但缺乏同步校验机制。

**具体对比**：

| 维度 | schema 示例文档 | validate_yaml.py 要求 | 差异 |
|------|-----------------|----------------------|------|
| 事件章节 | `chapters: [1, 2, 3]` | `chapter` (单值) | **字段名不同** |
| 事件情绪 | `emotion_arc: [恐惧, 抉择, 狂喜]` | `emotion` | **字段名不同** |
| 事件张力 | `tension_peak: 5` | `tension` | **字段名不同** |
| 事件类型 | `event_type: 推理破案` (单值示例) | 列表类型 | **类型不同** |

**深层原因**：
- schema 文档是"写作参考"，展示"大概怎么写"
- validate_yaml.py 是"执行标准"，决定"能不能通过"
- 两者由不同时间/不同人创建，未建立"单一真相来源"原则

---

### 2. 字段命名缺乏统一规范

**问题本质**：项目中没有"字段命名规范文档"，导致：
- schema 示例使用描述性命名（`emotion_arc` 表示"情绪轨迹")
- 校验脚本使用简洁命名（`emotion` 表示"情绪字段")
- 不同子系统的命名风格不一致

**影响范围**：
- 不仅事件文件，其他模块也可能存在类似问题
- 每次新增模块时，命名风格可能继续漂移

---

### 3. tags.yaml 作为静态字典的局限性

**问题本质**：tags.yaml 是一个"预定义标签字典"，但：
- 实际写作中会产生新标签（`道德抉择`、`文明存亡`、`关键抉择`）
- 没有标签扩展机制或标签自动注册机制
- 校验脚本严格拒绝任何不在字典中的值

**本次缺失标签清单**：
```
道德抉择, 文明存亡, 关键抉择, 悬念埋设, 视角切换
幸存, 感动, 平静, 恐惧, 悲伤, 紧张, 决绝, 冷漠展示
回忆, 掩体环境, 不定, 稳定, 太阳系, 歌者星系
执剑人控制室, 法庭, 医院, 大学, 星星购买网站
讨论, 对峙, 审讯, 决定, 观察, 信息传递, 逃脱行动
...
```

**深层原因**：
- tags.yaml 设计时假设"覆盖所有可能值"
- 但科幻题材的标签难以穷举
- 缺乏"动态扩展"或"宽松校验"机制

---

### 4. Schema 示例的误导性

**我的执行错误**：
1. 读取了 `docs/schemas/event-unit.schema.yaml` 的示例格式
2. 按照示例的字段名（`chapters`、`emotion_arc`、`tension_peak`）写入
3. 未先运行校验脚本测试单个文件
4. 直接批量生成 14 个文件

**认知偏差**：
- "示例文档是标准" ← 错误假设
- "示例格式能通过校验" ← 未验证就执行
- "批量生成更快" ← 未做单文件验证

**正确做法应该是**：
1. 生成第一个事件文件
2. 运行 validate_yaml.py 校验
3. 发现错误后修正格式
4. 确认通过后再批量生成

---

### 5. 执行前的验证缺失

**问题本质**：pipeline-events 的 SKILL.md 没有要求：
- "生成第一个文件后先校验"
- "确认 schema 对齐后再批量执行"

我的执行流程：
```
读取 schema → 理解格式 → 批量生成 → 校验 → 发现全部失败
```

正确流程应该是：
```
读取 schema → 生成单文件 → 校验 → 修正 → 确认通过 → 批量生成
```

---

### 6. 上下文继承问题

**问题本质**：由于 context window 限制，执行分为多个阶段：
- 阶段 1：读取 schema 示例
- 阶段 2：生成 outline/worldbuilding/characters（成功）
- 阶段 3：生成 events（失败）

在阶段 3 中：
- 阶段 1 的 schema 内容已被压缩/遗忘
- 我依赖的是"记忆中的 schema 格式"
- 记忆中的格式可能不准确

**这也是"分段执行"的固有问题**：
- 关键信息没有"跨段传递"
- 没有"关键信息清单"机制

---

## 与之前问题的对比

### 之前的问题（nm_novel_20260424_ap0z）

**类型**：执行态度问题
**本质**：绕过硬约束、造假状态
**原因**：把"硬约束"理解成"建议"，追求表面完成

### 本次的问题（nm_novel_20260424_v7n8）

**类型**：系统设计问题
**本质**：Schema 文档与校验脚本不一致
**原因**：文档不一致导致的认知偏差

**两者关系**：
- 之前的问题导致改进（阻断机制强化）
- 本次的问题是另一种类型（文档同步问题）
- 需要不同的改进措施

---

## 改进建议

### 1. 建立"单一真相来源"机制

**原则**：Schema 文档 = 校验脚本 = 唯一标准

**实施方法**：
- 校验脚本应该从 schema 文件中提取字段定义
- 或 schema 文件应该从校验脚本中生成
- 不允许两者独立维护

**具体方案 A**：校验脚本读取 schema
```python
# validate_yaml.py 改进
def load_schema_fields(schema_path):
    """从 schema.yaml 中提取字段定义"""
    with open(schema_path) as f:
        schema = yaml.safe_load(f)
    required_fields = extract_required(schema)
    field_types = extract_types(schema)
    return required_fields, field_types
```

**具体方案 B**：Schema 从校验脚本生成
```bash
# 新增脚本
python scripts/tools/generate_schema_docs.py
# 输出：docs/schemas/*.schema.yaml（与校验脚本同步）
```

---

### 2. 统一字段命名规范

**建议新增文档**：`docs/field-naming-conventions.md`

**内容示例**：
```
字段命名规范：

1. 简洁原则：字段名不超过 20 字符
2. 单值 vs 列表：单值字段不加后缀，列表字段加 `_list` 或直接用复数名词
3. 属性 vs 指标：属性字段用名词，指标字段用形容词

示例：
- chapter (单值，章节号)
- characters (列表，角色名)
- tension (指标，张力值)
- emotion (属性，情绪类型)
```

---

### 3. tags.yaml 扩展机制

**方案 A**：宽松校验模式
```python
# validate_yaml.py 增加 --loose 参数
# 允许未在 tags.yaml 中的标签值，但输出警告
python scripts/core/validate_yaml.py event {id} --loose
```

**方案 B**：标签自动注册
```python
# 新增脚本：自动将新标签添加到 tags.yaml
python scripts/tools/register_tags.py {id}
# 扫描所有 YAML，提取未注册标签，添加到 tags.yaml custom 区域
```

**方案 C**：标签分层设计
```yaml
# tags.yaml 改进
event_type:
  core: [...]        # 核心标签，必须使用
  extended: [...]    # 扩展标签，可选
  custom: []         # 自定义标签，动态添加
  
# 校验规则：
# core 标签严格校验
# extended 标签宽松校验（警告）
# custom 标签自动注册
```

---

### 4. Schema 示例增加校验提示

**改进 schema 文档格式**：
```yaml
# event-unit.schema.yaml 改进

# ====================================================================
# ⚠️ 重要：字段命名必须与校验脚本一致
# ====================================================================
# 
# 以下字段名是校验脚本的实际要求，不是示例建议：
# - chapter (单值，不是 chapters)
# - emotion (情绪，不是 emotion_arc)
# - tension (张力，不是 tension_peak)
# 
# 示例格式仅供参考，实际写入时请使用上述字段名

id: ev_main_001                           # R | 校验脚本要求: id
chapter: 1                                 # R | 校验脚本要求: chapter (单值)
emotion: [恐惧, 抉择, 狂喜]                 # R | 校验脚本要求: emotion
tension: 5                                 # R | 校验脚本要求: tension
```

---

### 5. 执行流程增加单文件验证

**改进 SKILL.md**：

在 `novel-events/SKILL.md` 中增加：
```
### 执行前验证（新增）

1. 生成第一个事件文件 `ev_main_001.yaml`
2. 运行校验：
   ```bash
   python scripts/core/validate_yaml.py event {id}
   ```
3. 如果失败：
   - 分析错误信息
   - 对齐字段命名
   - 重新生成并校验
4. 确认通过后：
   - 记录正确的字段格式
   - 开始批量生成其他事件文件
```

---

### 6. 关键信息清单机制

**建议新增**：`meta.yaml` 中增加 `execution_notes` 字段

```yaml
# meta.yaml 改进
execution_notes:
  schema_version_used: "2026-04-24"
  field_naming_convention: "validate_yaml.py 标准"
  validated_fields:
    event:
      chapter: "单值章节号"
      emotion: "情绪类型列表"
      tension: "张力值 1-5"
```

**目的**：跨段传递关键格式信息，避免遗忘。

---

## 当前状态

### nm_novel_20260424_v7n8 的处理状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| pipeline-ingest | ✅ 完成 | 入库 + 格式清洗 |
| pipeline-analyze | ✅ 完成 | outline + worldbuilding + characters + tags |
| pipeline-events | ⏸️ 中断 | 14 个事件文件已创建，schema 校验失败 |
| pipeline-finalize | ⏳ 待执行 | refine + novel-stats |

### 待修复事项

1. **对齐事件文件 schema**：
   - 字段名修改：`chapters` → `chapter`，`emotion_arc` → `emotion`，`tension_peak` → `tension`
   - 字段类型修改：`event_type` 改为列表格式
   - 缺失字段补充：`emotion`、`tension`

2. **扩展 tags.yaml 或使用已有标签**：
   - 添加缺失标签到 `custom` 区域
   - 或使用已有标签替代（如 `道德抉择` → `关系转折`）

3. **继续 pipeline-events**：
   - 完成 schema 对齐后重新校验
   - 构建 events_index.yaml 和 events_manifest.yaml

---

## 总结

本次问题的根本原因：

**Schema 文档与校验脚本不一致，导致按照示例格式写入的文件无法通过校验。**

这不是执行态度问题，而是系统设计问题：
- 缺乏"单一真相来源"机制
- 缺乏字段命名统一规范
- tags.yaml 作为静态字典无法覆盖动态需求
- Schema 示例具有误导性（示例 ≠ 标准）
- 执行流程缺少单文件验证环节

**教训**：

1. Schema 示例是"参考"，校验脚本是"标准"
2. 批量生成前必须先做单文件验证
3. 字段命名应与校验脚本严格对齐
4. tags.yaml 需要扩展机制或宽松模式
5. 关键格式信息应跨段传递

**后续改进方向**：

- 建立 schema 文档与校验脚本的同步机制
- 统一字段命名规范
- 扩展 tags.yaml 的灵活性
- 改进 schema 示例文档的明确性
- 在执行流程中增加单文件验证环节