# Standard 模式 Insights 章节上限设计

## 背景

`nm pipeline full` 和 `nm pipeline continue` 默认使用 `standard` 模式。当前编排器在该模式下调用 `insights` 时不传章节范围，因此会对 `chapters.yaml` 中全部章节生成 L2 深度分析。长篇小说可能包含上千章，这会显著增加运行时间与 API 消耗，也让可选增强层阻塞基础素材的可用时间。

`refine` 与 `insights` 是两个不同阶段：`refine` 基于全书 L1 章级数据执行本地统计、结构角色推断和向量化；本次只限制 `standard` 模式自动触发的 `insights`，不限制 L1 分析或 `refine`。

## 目标

- `standard` 模式自动生成开头 100 章的 insights。
- 章节上限由 `config/settings.yaml` 管理，避免业务代码硬编码。
- `fast` 模式继续跳过 insights。
- `deep` 模式保持当前全量 core insights 行为，不在本次实现关键章节采样。
- 独立命令 `nm pipeline insights <id> --start N --end M` 的显式范围行为保持不变。
- `full` 与 `continue` 使用同一编排规则，避免恢复运行重新尝试全书 insights。

## 非目标

- 不实现全书关键章节识别或分层采样。
- 不改变 `nm pipeline analyze --start/--end` 的现有语义。
- 不改变 `chapter_insights` 的 schema、文件布局、检索方式或数据库同步边界。
- 不删除或重写已经生成的 insight 文件。
- 不改变 `refine` 对全书 L1 数据的统计范围。

## 方案比较

### 方案 A：配置驱动的运行模式上限（采用）

在 `config/settings.yaml` 增加 `INSIGHTS_STANDARD_CHAPTER_LIMIT: 100`。运行模式解析时读取该配置，为 `standard` 暴露自动 insights 的结束章节；编排器把该范围传给 `run_insights_stage`。

优点是边界清晰、可通过配置调整为 80 或其他数值，并且 `full`、`continue` 共用同一行为。缺点是运行模式对象会增加一个范围字段。

### 方案 B：编排器写死 100

直接在 `_stage_specs` 中传入 `end_ch=100`。改动最少，但阈值散落在业务代码中，不符合项目配置约定，也不利于后续调整。

### 方案 C：开头 100 章加关键章节采样

保留开篇覆盖，同时从全书选择转折、高潮和结局章节。检索覆盖更好，但当前 `INSIGHTS_KEY_CHAPTER_RATE` 只有运行模式元数据，没有关键章节选择与完成度契约；本次引入会扩大设计和测试范围。

## 详细设计

### 配置与运行模式

`config/settings.yaml` 增加：

```yaml
INSIGHTS_STANDARD_CHAPTER_LIMIT: 100
```

`RuntimeMode` 增加 `core_insight_chapter_limit: int | None`：

- `fast`：`0`，但阶段仍由 `include_core_insights=False` 禁用。
- `standard`：读取 `INSIGHTS_STANDARD_CHAPTER_LIMIT`，默认值为 100。
- `deep`：`None`，表示不限制 core insights 范围。

配置值必须是正整数。若配置缺失则使用 100；若值不是正整数，运行模式解析应抛出带配置键名称的 `ValueError`，避免静默退化为全量分析。

### 编排与数据流

`_stage_specs` 只解析一次运行模式，并在 insights 阶段调用中传递范围：

```text
full / continue
  → get_runtime_mode(mode)
  → standard: start_ch=1, end_ch=配置上限
  → run_insights_stage(...)
  → generate_chapter_insights 仅筛选范围内 chapters
```

`analyze` 仍按现有 CLI 参数运行；没有显式 `--start/--end` 时分析全书。`outline`、`worldbuilding`、`characters`、`tags` 和 `refine` 继续消费全书 L1 产物。

`continue --mode standard` 即使面对已经包含全书 `chapters.yaml` 的素材，也只检查和补齐开头配置范围内的 insight 文件。范围外已有文件保留，但不参与本次阶段的 expected/succeeded/failed 计数。

### 独立 Insights 命令

`nm pipeline insights` 不经完整流水线的运行模式默认上限。以下命令仍明确表示用户要求的范围：

```bash
nm pipeline insights nm_xxx
nm pipeline insights nm_xxx --start 1 --end 100
nm pipeline insights nm_xxx --start 300 --end 350
```

第一条仍允许全量执行；后两条严格尊重显式范围。这样自动流水线有安全默认值，手动命令仍保留完整控制能力。

## 错误处理与兼容性

- 已有素材和 insight 文件不迁移、不删除。
- 有效的前 100 章 insight 继续被断点续传逻辑复用。
- 前 100 章内有缺失或无效文件时，只重试这些文件。
- 配置非法时在创建流水线计划前失败，错误信息包含 `INSIGHTS_STANDARD_CHAPTER_LIMIT`。
- `deep` 保持当前全量行为；由于独立 deep 生成器尚未实现，文档继续如实说明这一限制。

## 测试策略

1. 运行模式单元测试：验证 `standard` 默认上限为 100，`fast` 为禁用，`deep` 为无限制。
2. 配置校验测试：验证非正整数会抛出明确错误。
3. 编排器契约测试：替换 `run_insights_stage` 为记录参数的测试替身，验证 `standard` 传入 `start_ch=1, end_ch=100`。
4. 编排器契约测试：验证 `deep` 传入 `start_ch=None, end_ch=None`。
5. 回归测试：验证独立 `pipeline insights --start/--end` 仍传递显式范围。
6. 文档检查：更新用户手册与架构说明，明确 automatic standard、manual insights 和 refine 三者边界。

## 成功标准

- 新素材执行 `nm pipeline full ./novel.txt --mode standard` 时，L1 仍覆盖全书，insights 的 expected 数不超过 100。
- 已有全书 L1 素材执行 `nm pipeline continue <id> --mode standard` 时，不再尝试补齐第 101 章及以后 insights。
- `nm pipeline full ./novel.txt --mode fast` 仍不执行 insights。
- `nm pipeline full ./novel.txt --mode deep` 保持当前全量 core insights 行为。
- `nm pipeline insights <id> --start 1 --end 80` 仍只处理前 80 章。
