# 真人操作测试案例（300 例）

> 模拟真实用户在日常使用中可能遇到的误操作、异常事件、边界情况。
> 每个案例都是"某个人在某天真的会这么干"的事件。

---

## 一、文件误删与恢复（TC-RO-001 ~ TC-RO-040）

### 1.1 事件 YAML 误删（TC-RO-001 ~ TC-RO-010）

| ID | 操作事件 | 操作步骤 | 预期恢复方式 |
|----|---------|---------|-------------|
| TC-RO-001 | 手动删了一个事件文件 ev0015.yaml | `rm data/novels/nm_xxx/events/ev0015.yaml` | git checkout 恢复，或从 SQLite 导出数据手工重建 |
| TC-RO-002 | 误删了整个 events/ 文件夹 | `rm -rf data/novels/nm_xxx/events/` | git checkout 恢复整个文件夹，或从备份恢复 |
| TC-RO-003 | 用 Finder/资源管理器拖动 events 文件夹到回收站 | GUI 操作删除 | 从回收站恢复，然后运行 build-index 重建索引 |
| TC-RO-004 | 清理磁盘空间时误删了某本小说的文件夹 | `rm -rf data/novels/nm_novel_20260405_s4t1/` | git checkout 恢复，同时需要检查 index.yaml 是否仍有该条目 |
| TC-RO-005 | 删了事件文件但 SQLite 中还有记录 | 删除 ev0001.yaml 后没有重建索引 | 运行 build_db.py 重建 SQLite，确保 YAML 和 DB 一致 |
| TC-RO-006 | 批量删了最后 20 个事件文件想重做 | `rm data/novels/nm_xxx/events/ev018*` | 重新运行 novel-events 拆分对应章节范围 |
| TC-RO-007 | 误删 meta.yaml | `rm data/novels/nm_xxx/meta.yaml` | git checkout 恢复；若无版本控制，从 index.yaml 信息手工重建 |
| TC-RO-008 | 误删 source.txt（清洗后原文） | `rm data/novels/nm_xxx/source.txt` | 从 source.raw.txt（原始备份）恢复，重新运行 source-format |
| TC-RO-009 | 误删 source.raw.txt（原始备份） | `rm data/novels/nm_xxx/source.raw.txt` | source.txt 仍在可用，但失去原始对照；需从原文件重新入库 |
| TC-RO-010 | 误删 data/tags.yaml（全局标签字典） | `rm data/tags.yaml` | git checkout 恢复；无版本控制则需手动重建，影响所有后续操作 |

### 1.2 索引与数据库误删（TC-RO-011 ~ TC-RO-020）

| ID | 操作事件 | 操作步骤 | 预期恢复方式 |
|----|---------|---------|-------------|
| TC-RO-011 | 误删 material.db | `rm data/material.db` | 运行 `python scripts/core/build_db.py` 从 YAML 重建 |
| TC-RO-012 | 误删 index.yaml（素材路由表） | `rm data/index.yaml` | git checkout 恢复；或扫描 data/novels/ 目录重建 |
| TC-RO-013 | 误删 events_index.yaml（倒排索引） | `rm data/novels/nm_xxx/events_index.yaml` | 运行 build-index 重建 |
| TC-RO-014 | 误删 events_manifest.yaml（事件清单） | `rm data/novels/nm_xxx/events_manifest.yaml` | 运行 build-index 重建 |
| TC-RO-015 | 误删 plot_index.yaml（全局剧情索引） | `rm data/plot_index.yaml` | 运行 build-index 对任一小说重建，会自动聚合全局 |
| TC-RO-016 | 误删 evaracter_index.yaml | `rm data/evaracter_index.yaml` | 同上，build-index 会自动聚合 |
| TC-RO-017 | 误删 chapter_index.yaml | `rm data/novels/nm_xxx/chapter_index.yaml` | 重新运行 source-format 生成 |
| TC-RO-018 | 同时删了 material.db 和 events_index.yaml | 两个文件都删了 | 先 build-index 生成 YAML 索引，再 build_db.py 重建 SQLite |
| TC-RO-019 | 误删 format_report.yaml | `rm data/novels/nm_xxx/format_report.yaml` | 重新运行 source-format 生成，不影响其他文件 |
| TC-RO-020 | 误删 stats.html | `rm data/novels/nm_xxx/stats.html` | 重新运行 novel-stats 生成 |

### 1.3 分析文件误删（TC-RO-021 ~ TC-RO-030）

| ID | 操作事件 | 操作步骤 | 预期恢复方式 |
|----|---------|---------|-------------|
| TC-RO-021 | 误删 outline.yaml | `rm data/novels/nm_xxx/outline.yaml` | git checkout 或重新运行 novel-outline |
| TC-RO-022 | 误删 worldbuilding.yaml | `rm data/novels/nm_xxx/worldbuilding.yaml` | git checkout 或重新运行 novel-worldbuilding |
| TC-RO-023 | 误删 evaracters.yaml | `rm data/novels/nm_xxx/evaracters.yaml` | git checkout 或重新运行 novel-evaracters |
| TC-RO-024 | 误删小说级 tags.yaml（非全局 tags.yaml） | `rm data/novels/nm_xxx/tags.yaml` | git checkout 或重新运行 novel-tags |
| TC-RO-025 | 在 refine 之后误删精调文件，想回到 refine 前的版本 | 删了精调后的 outline.yaml | git checkout 到 refine 前的提交版本 |
| TC-RO-026 | 同时误删 outline + evaracters + tags | 三个分析文件一起被删 | git checkout 或重新运行 pipeline-analyze |
| TC-RO-027 | 清空整个小说文件夹后在回收站找回 | 从回收站恢复文件夹 | 检查文件完整性，运行 validate_yaml 校验事件 |
| TC-RO-028 | 误删 .config/pipeline_status.json | `rm data/.config/pipeline_status.json` | 系统重新创建空状态文件，pipeline 从头检查状态 |
| TC-RO-029 | 误删 .config/llm_config.json | `rm data/.config/llm_config.json` | 系统使用默认配置或提示重新配置 |
| TC-RO-030 | 误删 scripts/core/ 下的脚本文件 | `rm scripts/core/searev.py` | git checkout 恢复，这些脚本在版本控制中 |

### 1.4 批量误操作（TC-RO-031 ~ TC-RO-040）

| ID | 操作事件 | 操作步骤 | 预期恢复方式 |
|----|---------|---------|-------------|
| TC-RO-031 | `rm -rf data/novels/*` 删了所有小说 | 把所有小说数据都删了 | git checkout 恢复；或从远程仓库 clone |
| TC-RO-032 | `rm -rf data/` 删了整个数据目录 | 连 tags.yaml、index.yaml 都删了 | git checkout 恢复全部，然后 build_db.py 重建 SQLite |
| TC-RO-033 | 用 find 命令误删了所有 .yaml 文件 | `find . -name "*.yaml" -delete` | git checkout 恢复所有 YAML 文件 |
| TC-RO-034 | git reset --hard 丢失未提交的事件 | 大量新拆分的事件未提交就 reset 了 | 用 `git reflog` 找回，或重新运行事件拆分 |
| TC-RO-035 | 误操作 git clean -fd 清除未追踪文件 | 新生成但未 git add 的文件被清除 | git reflog 或重新生成 |
| TC-RO-036 | 把 A 小说的 events 文件夹覆盖到了 B 小说 | `cp -rf novels/A/events/ novels/B/events/` | 从 git 恢复 B 的 events，重新 build-index |
| TC-RO-037 | 全局替换操作把 YAML 中的某个标签值改错了 | IDE 全局替换影响了多个文件 | git diff 查看改动范围，git checkout 恢复受影响文件 |
| TC-RO-038 | 误用 sed 批量修改了事件 YAML 的 tension 字段 | `sed -i 's/tension: 5/tension: 1/g' *.yaml` | git checkout 恢复，运行 validate_yaml 校验 |
| TC-RO-039 | 磁盘空间满了导致写入不完整 | YAML 文件写到一半磁盘满了 | 清理磁盘空间，删除不完整文件，重新执行该批次 |
| TC-RO-040 | 在 pipeline 执行过程中强制关机 | 正在写事件文件时断电 | 开机后检查最后一批事件的完整性，continue 恢复 |

---

## 二、YAML 格式错误与修正（TC-RO-041 ~ TC-RO-080）

### 2.1 手动编辑 YAML 引入的格式错误（TC-RO-041 ~ TC-RO-060）

| ID | 操作事件 | 错误示例 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-041 | 手动编辑事件 YAML 时缩进不一致 | 混用 Tab 和空格 | validate_yaml 报错定位到具体行 |
| TC-RO-042 | 忘了在冒号后加空格 | `title:没有空格` | YAML 解析失败，报错提示行号 |
| TC-RO-043 | 中文引号没用单引号包裹 | `note: 他说"你好"` | YAML 解析失败或值被截断 |
| TC-RO-044 | summary 多行文本没有用 >- 标记 | 直接换行写 | 换行后的内容丢失或被误解析 |
| TC-RO-045 | tension 写成了字符串而非数字 | `tension: "5"` | validate_yaml 报类型错误或自动转换 |
| TC-RO-046 | tension 写成小数 | `tension: 3.5` | validate_yaml 报错，tension 必须为整数 |
| TC-RO-047 | 列表格式写错 | `emotion: 燃, 悲伤`（缺少方括号） | YAML 解析为字符串而非列表 |
| TC-RO-048 | 多了一个冒号导致嵌套层级错误 | `event_type: : 对决` | YAML 解析错误 |
| TC-RO-049 | 遗漏了必填字段 id | 编辑时误删了 id 行 | validate_yaml 报缺少必填字段 |
| TC-RO-050 | 遗漏了必填字段 chapter | 编辑时误删了 chapter 行 | validate_yaml 报缺少必填字段 |
| TC-RO-051 | id 格式不对（不是 ev{NNNN}_s{NN}） | `id: event_15` | validate_yaml 报 ID 格式错误 |
| TC-RO-052 | 标签值前面多了横杠（列表语法写在不该写的地方） | `pacing: - 快` | YAML 解析为意外的嵌套结构 |
| TC-RO-053 | 用了中文冒号代替英文冒号 | `title：黎明之战` | YAML 无法解析键值对 |
| TC-RO-054 | 布尔值被 YAML 隐式转换 | `scale: no`（被解析为 false） | 应使用引号包裹 `scale: "no"` |
| TC-RO-055 | 数组中混入了 null 值 | `emotion: [燃, , 悲伤]` | 列表中出现 None，校验报错 |
| TC-RO-056 | 重复的键名 | 同一文件有两个 `title:` 行 | 后者覆盖前者，validate_yaml 应告警 |
| TC-RO-057 | 使用了 BOM 头的 UTF-8 编码保存 | Windows 记事本保存添加 BOM | YAML 解析可能失败或第一行键名无法识别 |
| TC-RO-058 | 行尾有不可见的空白字符 | 行末有 \r\n 混合换行 | 标签值尾部多出空格，检索不到 |
| TC-RO-059 | 使用了 YAML 注释但注释格式错 | `# 这是注释` 前面没有空格或换行 | 注释与值粘连，解析异常 |
| TC-RO-060 | 整个文件是空的（0 字节） | 编辑器保存了空文件 | build-index 跳过空文件，不崩溃 |

### 2.2 Meta 和配置文件格式错误（TC-RO-061 ~ TC-RO-070）

| ID | 操作事件 | 错误示例 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-061 | meta.yaml 中 status 写了非法值 | `status: doing`（应为 raw/outlined/complete 等） | 系统报错或 pipeline 无法判断状态 |
| TC-RO-062 | meta.yaml 中 material_id 与文件夹名不匹配 | 文件夹名 nm_xxx 但 meta 中写成 nm_yyy | 系统检测到不一致并报错 |
| TC-RO-063 | index.yaml 中 folder 路径写错 | `folder: novels/nm_xxx_typo` | 系统访问不到文件夹，检索失败 |
| TC-RO-064 | index.yaml 中注册了两条 ID 相同的记录 | 重复条目 | 系统检测到重复并报错 |
| TC-RO-065 | tags.yaml 中维度名拼写错误 | `scnee_type` 代替 `event_type` | 使用该维度的校验全部失败 |
| TC-RO-066 | tags.yaml 格式被破坏（如缺少 values 键） | `event_type: {description: "事件类型"}` | 系统报错，标签校验无法进行 |
| TC-RO-067 | pipeline_status.json 格式不合法 | JSON 语法错误 | 系统重新初始化状态文件 |
| TC-RO-068 | llm_config.json 中配置了错误的 API 地址 | `"api_url": "https://invalid.example.com"` | LLM 调用失败，提示网络错误 |
| TC-RO-069 | chapter_index.yaml 中章节名有拼写错误 | `第1张 开始` 代替 `第1章 开始` | 事件中 chapter 字段与 chapter_index 不匹配 |
| TC-RO-070 | outline.yaml 被手动编辑成了非法 YAML | 编辑时破坏了结构 | 前端 MaterialDetail 加载报错或兜底渲染 |

### 2.3 自动生成内容的格式问题（TC-RO-071 ~ TC-RO-080）

| ID | 操作事件 | 错误示例 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-071 | LLM 生成的事件 YAML 包含多余的 Markdown 标记 | 开头有 ```yaml，结尾有 ``` | 解析时自动去除 Markdown 围栏 |
| TC-RO-072 | LLM 生成的 summary 超长（>500 字） | summary 写成了一整段分析 | 应有长度校验，提示截断或重新生成 |
| TC-RO-073 | LLM 生成了嵌套格式而非扁平格式 | 使用了旧的 content/people/emotion 分组 | build_db.py 的 _flatten_event() 兼容处理 |
| TC-RO-074 | LLM 在 title 中使用了编号 | `title: 事件3` | quality_audit 检测到并告警 |
| TC-RO-075 | LLM 给所有事件都打了相同的 emotion 标签 | 10 个事件全是 `emotion: [平静]` | quality_audit 检测到标签多样性不足 |
| TC-RO-076 | LLM 给出了 tags.yaml 中不存在的标签值 | `event_type: [超自然]`（不在合法值中） | validate_yaml 检测到非法标签值 |
| TC-RO-077 | LLM 遗漏了 evaracters 字段 | 事件 YAML 中无 evaracters 列表 | validate_yaml 报缺少必填字段 |
| TC-RO-078 | LLM 输出的 YAML 有语法错误 | 例如列表缩进不对 | 写入前应先 yaml.safe_load 验证 |
| TC-RO-079 | LLM 把 tension 写成了中文 | `tension: 三` | validate_yaml 报类型错误 |
| TC-RO-080 | LLM 输出了空的事件 YAML | 只有注释没有内容 | 跳过空文件，不崩溃，报告问题 |

---

## 三、Pipeline 中断与恢复（TC-RO-081 ~ TC-RO-120）

### 3.1 Pipeline 各阶段中断（TC-RO-081 ~ TC-RO-100）

| ID | 操作事件 | 中断方式 | 预期恢复方式 |
|----|---------|---------|-------------|
| TC-RO-081 | pipeline-ingest 执行到一半关闭终端 | Ctrl+C 或关闭终端 | 检查 meta.yaml 是否已生成，若有则继续；若无则重新运行 |
| TC-RO-082 | source-format 清洗过程中 Ctrl+C | 强制中断 | source.txt 可能不完整，需删除后重新运行 |
| TC-RO-083 | novel-outline 生成大纲时 LLM 超时 | API 调用超时 | 重新运行 novel-outline，不影响已有文件 |
| TC-RO-084 | novel-evaracters 执行一半断网 | 网络中断 | 检查 evaracters.yaml 是否完整，不完整则删除重做 |
| TC-RO-085 | novel-tags 执行完但写入失败 | 磁盘写入错误 | 重新运行 novel-tags |
| TC-RO-086 | pipeline-analyze 在 worldbuilding 步骤中断 | 关闭 IDE | outline.yaml 已生成，从 worldbuilding 步骤恢复 |
| TC-RO-087 | novel-events 在第 15 批中断 | 长时间运行后 token 耗尽 | continue 模式从第 16 批恢复 |
| TC-RO-088 | novel-events 在第 30 批时开新对话 | 按建议每 30 批分段 | 新对话 continue 从第 31 批开始 |
| TC-RO-089 | novel-events 在 all 模式中突然退出 | 浏览器崩溃 | meta.yaml 记录了最后完成的批次，continue 恢复 |
| TC-RO-090 | build-index 执行过程中 Ctrl+C | 强制中断 | YAML 索引可能不完整，重新运行 build-index |
| TC-RO-091 | refine 精调到一半中断 | 网络不稳定 | 检查哪些文件已精调，对未精调的文件重新运行 |
| TC-RO-092 | novel-stats 生成报告时中断 | Ctrl+C | 重新运行 novel-stats，覆盖不完整文件 |
| TC-RO-093 | pipeline-finalize 中断 | 关闭终端 | 检查 refine 是否完成，若完成则只运行 novel-stats |
| TC-RO-094 | full pipeline 在 analyze 阶段中断 | 长时间无响应后强制退出 | /novel-pipeline continue 从中断点恢复 |
| TC-RO-095 | full pipeline 在 events 阶段中断后开新对话 | 对话超长后换新对话 | /novel-pipeline continue [id] 从上次位置恢复 |
| TC-RO-096 | 同时运行两个 pipeline 处理同一本书 | 误开两个终端 | 应检测到冲突并阻止，或至少不破坏数据 |
| TC-RO-097 | 同时运行两个 pipeline 处理不同的书 | 并行处理两本小说 | 各自独立运行，互不影响 |
| TC-RO-098 | pipeline 执行到一半手动修改了事件文件 | 在 novel-events 运行中编辑了已生成的 YAML | 不影响后续批次，但修改可能在 build-index 时被检测到 |
| TC-RO-099 | pipeline 执行到一半手动修改了 meta.yaml 的 status | 把 status 从 outlined 改成了 raw | pipeline 可能回退到不正确的阶段 |
| TC-RO-100 | pipeline 执行到一半删除了 chapter_index.yaml | 事件拆分依赖此文件 | novel-events 无法确定章节名，报错停止 |

### 3.2 恢复事件验证（TC-RO-101 ~ TC-RO-120）

| ID | 操作事件 | 验证步骤 | 预期结果 |
|----|---------|---------|---------|
| TC-RO-101 | 中断恢复后检查事件文件连续性 | 查看 events/ 目录下文件编号是否连续 | 无缺失、无重复 |
| TC-RO-102 | 中断恢复后检查 meta.yaml 进度 | 读取 meta.yaml 中的 pipeline 相关字段 | 进度信息准确反映实际完成状态 |
| TC-RO-103 | 恢复后的事件与中断前的事件标签风格一致 | 对比中断前后的事件标签分布 | 风格连贯，不因换对话而突变 |
| TC-RO-104 | 恢复后 build-index 能正确处理所有事件 | 运行 build-index | 索引覆盖所有事件，包括中断前后的 |
| TC-RO-105 | 恢复后搜索能找到所有已处理的事件 | 搜索某个标签值 | 中断前后的事件都能被搜索到 |
| TC-RO-106 | 手动删除最后 5 个事件后 continue | 删了几个然后恢复 | 从删除后的位置重新拆分，不跳过 |
| TC-RO-107 | 修改了 meta.yaml 中的批次记录后 continue | 手动把 last_batev 改小 | 从修改后的位置重新拆分，可能重复 |
| TC-RO-108 | continue 时发现 source.txt 被修改过 | 有人编辑了原文 | 新事件基于修改后的原文拆分，可能与旧事件不一致 |
| TC-RO-109 | continue 时发现 tags.yaml 新增了标签值 | 中间更新了标签字典 | 新事件可以使用新标签值 |
| TC-RO-110 | continue 时发现 chapter_index.yaml 被修改 | 中间修正了章节名 | 新事件使用修正后的章节名，已有事件不变 |
| TC-RO-111 | 全部事件拆完后再 continue | 已经完成所有章节 | 系统提示已完成，不做重复工作 |
| TC-RO-112 | stage 模式指定执行 pipeline-events | `/novel-pipeline stage [id] events` | 仅执行事件拆分+索引阶段 |
| TC-RO-113 | stage 模式执行 finalize 但 events 未完成 | 事件拆分未完就跑精调 | 系统提示前置阶段未完成 |
| TC-RO-114 | quick 模式完成后切换到 full 模式 | 快速骨架后想补全 | 从 events 阶段继续，不重复 analyze |
| TC-RO-115 | pipeline 完成后重新运行 full | 已完成的书再跑一遍 | 全部覆盖重新生成，或提示已完成可选择跳过 |
| TC-RO-116 | 中断后手动补了几个事件文件再 continue | 自己写了事件 YAML 放进去 | continue 跳过已有编号，继续后续章节 |
| TC-RO-117 | 事件文件编号有空洞后 build-index | ev0010 不存在但 ev0011 存在 | build-index 正常处理，不因编号不连续而失败 |
| TC-RO-118 | 修改了一个事件的标签后没有重建索引 | 改了标签但没 build-index | SQLite 搜索结果与 YAML 不一致直到重建 |
| TC-RO-119 | 批量修改事件标签后重建索引 | 改了 50 个事件的 emotion 标签 | build-index 全部更新，搜索结果正确 |
| TC-RO-120 | 添加新事件文件后不重建索引就搜索 | 手动写了新事件 | 新事件在 SQLite 中搜不到，YAML 索引中也没有 |

---

## 四、数据写错与修正（TC-RO-121 ~ TC-RO-170）

### 4.1 标签值写错（TC-RO-121 ~ TC-RO-140）

| ID | 操作事件 | 错误示例 | 修正方式 |
|----|---------|---------|---------|
| TC-RO-121 | 事件标签值拼写错误 | `emotion: [燃燃]`（多了一个字） | 手动修正 YAML，重新 build-index |
| TC-RO-122 | 标签维度名写错 | `scence_type` 代替 `event_type` | 手动修正，validate_yaml 会检测到 |
| TC-RO-123 | 单值字段误写为列表 | `pacing: [快]`（应为 `pacing: 快`） | build_db.py 取列表第一个值，但可能有信息丢失 |
| TC-RO-124 | 列表字段误写为单值 | `emotion: 燃`（应为 `emotion: [燃]`） | validate_yaml 报类型错误 |
| TC-RO-125 | tension 写成了 0 | `tension: 0`（有效范围 1-5） | validate_yaml 报超出范围 |
| TC-RO-126 | tension 写成了负数 | `tension: -1` | validate_yaml 报超出范围 |
| TC-RO-127 | evaracters 列表人名写错 | `evaracters: [张三三]`（正确应为张三） | 人物搜索找不到该事件，需手动修正 |
| TC-RO-128 | chapter 字段手写不从 chapter_index 拷贝 | `chapter: 第一章 开始`（index 中是"第1章 开始"） | validate_yaml 检测章节名不匹配 |
| TC-RO-129 | 多个事件 YAML 中使用了同一个 id | 两个文件都是 `id: ev0001` | build-index 检测到重复 ID 报错 |
| TC-RO-130 | 事件文件名与内部 id 不匹配 | 文件名 ev0001.yaml 但 id 写成 ev0002 | validate_yaml 检测到不一致 |
| TC-RO-131 | 用 tag-merge 合并标签后有遗漏 | 个别文件的旧标签值没有被替换 | 再次运行 tag-merge 或手动搜索修正 |
| TC-RO-132 | tag-add 添加了一个不恰当的标签值 | 加了 `emotion: [快乐到变形]` | 手动编辑 tags.yaml 删除该值 |
| TC-RO-133 | 事件 summary 内容与实际章节完全不符 | summary 描述的是另一个事件 | 手动修正 summary，参照 source.txt 对应行号 |
| TC-RO-134 | 事件 title 含有非法字符 | `title: 事件/杀戮`（斜杠可能影响文件名） | 手动修正，避免使用文件系统不支持的字符 |
| TC-RO-135 | 人物 role 字段写了非标准值 | `role: 小角色`（应为 protagonist/antagonist/supporting 等） | 手动修正为标准值 |
| TC-RO-136 | 人物 arevetype 写了 tags.yaml 中没有的原型 | `arevetype: 超级战士` | 检查是否需要 tag-add 或修正为已有值 |
| TC-RO-137 | worldbuilding 中力量体系层级顺序搞反 | 把最高级写在了最低级位置 | 手动调整 worldbuilding.yaml 中的层级顺序 |
| TC-RO-138 | outline 中章节范围与实际不符 | 大纲标注第一幕到第30章，实际只有25章 | 手动修正 outline.yaml 或 refine 后自动修正 |
| TC-RO-139 | 全局替换时不小心改了不该改的内容 | IDE 替换"张三"变"张三丰"，影响了不相关文件 | git diff 查看，git checkout 恢复不该改的文件 |
| TC-RO-140 | 手动修改了 material.db 中的数据 | 直接 SQL UPDATE 修改了记录 | 数据与 YAML 不一致，需要 build_db.py 重建 |

### 4.2 配置写错（TC-RO-141 ~ TC-RO-155）

| ID | 操作事件 | 错误示例 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-141 | index.yaml 中 material_id 格式不规范 | `id: my_novel`（不符合 nm_{type}_{date}_{rand} 格式） | 系统应能检测到非规范 ID |
| TC-RO-142 | index.yaml 中 type 字段写了不存在的类型 | `type: screenplay`（目前只支持 novel） | 系统提示不支持的类型或允许扩展 |
| TC-RO-143 | meta.yaml 中 source 指向不存在的文件 | `source: source_v2.txt`（实际文件名是 source.txt） | pipeline 找不到原文时报错 |
| TC-RO-144 | meta.yaml 中 formatted 字段与实际状态不符 | `formatted: true` 但实际未做格式清洗 | source-format 检查后覆盖，或 pipeline 重新判断 |
| TC-RO-145 | pipeline_status.json 中的进度记录被手动篡改 | 把某本书的状态从 events 改成 complete | pipeline 跳过后续步骤，导致数据不完整 |
| TC-RO-146 | 后端 main.py 中 CORS 配置错误 | 缺少前端域名 | 前端 API 请求被 CORS 拦截 |
| TC-RO-147 | 前端 API client 中 baseURL 写错 | `baseURL: "http://localhost:9999"` | 所有 API 请求失败，前端空白 |
| TC-RO-148 | vite.config.ts 中 proxy 配置错误 | 代理目标地址写错 | 开发环境下 API 请求 404 |
| TC-RO-149 | requirements.txt 中依赖版本冲突 | 两个包要求不兼容的 numpy 版本 | pip install 失败 |
| TC-RO-150 | package.json 中依赖缺失 | 缺少 @testing-library/jest-dom | Vitest 测试无法运行 |
| TC-RO-151 | tsconfig.json 中 paths 配置错误 | `@` 别名指向错误目录 | 前端 import 找不到模块 |
| TC-RO-152 | .gitignore 没有忽略 material.db | 数据库文件被提交到 git | 影响协作，每次 pull 有冲突 |
| TC-RO-153 | .gitignore 没有忽略 node_modules | 意外提交了 node_modules | 仓库体积暴增 |
| TC-RO-154 | .gitignore 忽略了不该忽略的文件 | `*.yaml` 加入了 gitignore | 所有 YAML 文件都不被追踪 |
| TC-RO-155 | eslint 配置过于严格导致 CI 失败 | 新增代码不符合 lint 规则 | 修改代码或调整 lint 配置 |

### 4.3 事件批次修正（TC-RO-156 ~ TC-RO-170）

| ID | 操作事件 | 操作步骤 | 预期结果 |
|----|---------|---------|---------|
| TC-RO-156 | 发现第 5 批事件质量太差，想整批重做 | 删除 ev0041-ev0050 对应的所有事件文件 | 重新运行 novel-events 指定该章节范围 |
| TC-RO-157 | quality_audit 报告某批次标签雷同 | 审查后确认确实需要重做 | 删除该批文件，重新拆分 |
| TC-RO-158 | 手动修改了 3 个事件的标签后想验证 | 编辑了 YAML 文件 | 运行 validate_yaml 校验，通过后 build-index |
| TC-RO-159 | 事件拆分粒度太粗，一章只有 1 个事件 | 想把一个事件拆成两个 | 手动创建新的事件文件，调整 ID 编号 |
| TC-RO-160 | 事件拆分粒度太细，一章有 10 个事件 | 想合并几个事件 | 删除多余文件，合并内容到保留的文件中 |
| TC-RO-161 | 两本小说的事件 ID 意外冲突 | 不同小说生成了相同的 ev0001 | 事件 ID 应包含 material_id 前缀，确认不冲突 |
| TC-RO-162 | 修改了一个事件的 chapter 字段后索引对不上 | 改了章节名但 chapter_index 没更新 | 保持 chapter 字段与 chapter_index.yaml 一致 |
| TC-RO-163 | 批量修改了事件的 pov 字段 | 发现整本书 pov 标记错误 | 全局替换后运行 validate_yaml + build-index |
| TC-RO-164 | 在已完成的书中插入了新章节 | 作者更新了原文，中间新增了一章 | 需要重新 source-format + novel-events（受影响范围） |
| TC-RO-165 | 发现 source.txt 和 source.raw.txt 不同步 | 手动编辑了 source.txt 但没更新 raw | 二者可以不同（raw 是原始备份），但需记住哪个是权威 |
| TC-RO-166 | 多人同时编辑同一个事件文件 | A 和 B 都改了 ev0015.yaml | git merge 处理冲突或约定编辑锁 |
| TC-RO-167 | refine 后想回退到 refine 前的版本 | 精调结果不满意 | git checkout 到 refine 前的提交 |
| TC-RO-168 | novel-stats 统计数据与手动数不一致 | stats 显示 285 个事件，实际有 283 个文件 | 检查 stats 的数据来源，是否有空文件或格式错误 |
| TC-RO-169 | 删除了一本小说但忘了更新 index.yaml | 文件夹删了但注册还在 | 搜索时报路径不存在的错误 |
| TC-RO-170 | 重命名了小说文件夹但没更新 index.yaml | 改了文件夹名 | index.yaml 中的 folder 路径失效 |

---

## 五、前端操作与交互异常（TC-RO-171 ~ TC-RO-220）

### 5.1 页面加载与导航（TC-RO-171 ~ TC-RO-190）

| ID | 操作事件 | 操作步骤 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-171 | 后端未启动时打开前端 | 直接访问前端 URL | 显示连接错误提示，不白屏 |
| TC-RO-172 | 后端启动但数据库不存在时打开前端 | material.db 被删了 | 前端显示"暂无数据"而非报错 |
| TC-RO-173 | 打开 Dashboard 但没有任何素材入库 | 全新安装状态 | 显示空状态引导，提示如何入库 |
| TC-RO-174 | 打开 MaterialList 但 index.yaml 为空 | 没有注册素材 | 显示空列表，不崩溃 |
| TC-RO-175 | 打开 MaterialDetail 但该 ID 不存在 | URL 中的 ID 被手动改错 | 显示 404 或"素材不存在"提示 |
| TC-RO-176 | 打开 MaterialDetail 但缺少 outline.yaml | 只入库了没做分析 | 对应 Tab 显示"暂未生成"而非错误 |
| TC-RO-177 | 打开 MaterialDetail 但缺少 worldbuilding.yaml | 世界观文件不存在 | 对应 Tab 显示"暂未生成" |
| TC-RO-178 | 打开 MaterialDetail 但 stats.html 很大（>5MB） | 事件非常多的书 | 加载时有 loading 提示，不卡死 |
| TC-RO-179 | 快速连续切换 Tab | 在 MaterialDetail 中快速点击各个 Tab | 不出现数据混乱或闪烁 |
| TC-RO-180 | 浏览器后退/前进按钮导航 | 在各页面间使用浏览器导航 | 路由正确，页面正常加载 |
| TC-RO-181 | 直接在地址栏输入 URL 访问详情页 | 不通过列表点击，直接输入 URL | 页面正常加载对应素材 |
| TC-RO-182 | 刷新 EventSearev 结果页 | 搜索后刷新浏览器 | 搜索条件丢失，页面恢复到初始状态 |
| TC-RO-183 | 在 TagDictionary 页面滚动到底部 | 标签维度很多 | 页面平滑滚动，无性能问题 |
| TC-RO-184 | Settings 页面修改配置后不保存就离开 | 改了设置但未点保存 | 提示未保存或静默丢弃修改 |
| TC-RO-185 | 同时在两个浏览器标签页操作 | 两个标签页分别搜索和浏览 | 互不影响 |
| TC-RO-186 | 窄屏/手机端访问前端 | 缩小浏览器窗口 | 布局自适应或至少可用 |
| TC-RO-187 | 前端长时间空闲后操作 | 开着页面去吃饭回来操作 | API 请求正常，不因连接超时而失败 |
| TC-RO-188 | 打开 Upload 页面 | 访问上传页面 | 页面正常渲染，上传功能可用 |
| TC-RO-189 | 网络极慢时加载 Dashboard | 模拟 3G 网络 | 有 loading 状态，不超时崩溃 |
| TC-RO-190 | JavaScript 被禁用时访问前端 | 浏览器禁用 JS | 显示友好提示或降级渲染 |

### 5.2 搜索操作异常（TC-RO-191 ~ TC-RO-210）

| ID | 操作事件 | 操作步骤 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-191 | 搜索框输入为空直接搜索 | 不填任何条件点搜索 | 提示请输入条件或返回全部结果 |
| TC-RO-192 | 搜索框输入超长字符串 | 粘贴 10000 字文本搜索 | 不崩溃，截断或提示长度限制 |
| TC-RO-193 | 搜索框输入 HTML 标签 | `<script>alert(1)</script>` | 不执行脚本（XSS 防御） |
| TC-RO-194 | 搜索框输入 SQL 关键字 | `DROP TABLE events` | 不执行 SQL（注入防御） |
| TC-RO-195 | 快速连续点击搜索按钮 | 1 秒内点了 10 次 | 不重复发送请求，或取消前一次请求 |
| TC-RO-196 | 搜索过程中切换到其他页面 | 搜索还没返回就导航走了 | 不影响新页面加载，旧请求被取消 |
| TC-RO-197 | 标签多选后取消所有选择 | 先选了 3 个标签又全部取消 | 恢复到无筛选状态 |
| TC-RO-198 | 搜索条件组合不可能有结果 | 同时选 emotion=燃 AND emotion=悲伤 | 返回空结果，不报错 |
| TC-RO-199 | CharacterSearev 输入不存在的人物名 | 搜索"王五"但没有这个人物 | 返回空结果，提示"未找到" |
| TC-RO-200 | EventSearev 选择了所有标签维度 | 每个维度都选了值 | 返回严格满足所有条件的结果（可能为空） |
| TC-RO-201 | 搜索结果中点击某个事件查看详情 | 点击搜索结果卡片 | 跳转到对应素材详情页或展开详情 |
| TC-RO-202 | 搜索时后端正在 build-index | 索引重建中同时搜索 | 返回当前索引状态的结果或提示索引更新中 |
| TC-RO-203 | 搜索返回大量结果（>1000 条） | 宽泛的搜索条件 | 分页加载，不一次性渲染全部 |
| TC-RO-204 | 搜索后刷新页面 | 有结果时刷新 | 搜索状态丢失或通过 URL 参数保持 |
| TC-RO-205 | 在搜索结果中排序 | 按张力值排序 | 排序正确，不丢失结果 |
| TC-RO-206 | 前端发送了非法的查询参数 | 手动构造 URL 参数 | 后端校验参数合法性，返回 400 |
| TC-RO-207 | 后端搜索 API 返回空的 JSON | `{"events": []}` | 前端显示"无结果"而非空白 |
| TC-RO-208 | 后端搜索 API 返回格式不符预期 | 缺少必要字段 | 前端兜底渲染，不崩溃 |
| TC-RO-209 | 搜索时输入特殊 Unicode 字符 | 输入 emoji 或零宽字符 | 不崩溃，正常处理 |
| TC-RO-210 | 连续搜索不同条件 | 搜了 A 条件看结果再搜 B 条件 | 结果正确切换，不残留上次结果 |

### 5.3 上传与文件操作（TC-RO-211 ~ TC-RO-220）

| ID | 操作事件 | 操作步骤 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-211 | Upload 页面上传一个 .txt 文件 | 选择文件上传 | 成功上传，后端入库处理 |
| TC-RO-212 | Upload 页面上传一个 .docx 文件 | 选择 Word 文档 | 提示格式不支持或自动转换 |
| TC-RO-213 | Upload 页面上传一个 100MB 大文件 | 选择超大文件 | 有上传进度条，不超时 |
| TC-RO-214 | Upload 页面上传 0 字节文件 | 选择空文件 | 拒绝上传，提示文件为空 |
| TC-RO-215 | Upload 过程中取消上传 | 点击取消按钮 | 上传中止，无残留文件 |
| TC-RO-216 | Upload 过程中网络断开 | 拔网线 | 显示上传失败提示，可重试 |
| TC-RO-217 | 同时上传两个文件 | 连续选择两个文件上传 | 排队处理或并行处理，不互相影响 |
| TC-RO-218 | 上传文件名包含特殊字符 | `小说(v2).txt` 或 `小说 [完结].txt` | 正确处理，不因文件名异常失败 |
| TC-RO-219 | 上传后立即刷新 MaterialList | 上传完马上看列表 | 新入库的素材出现在列表中 |
| TC-RO-220 | 上传与 pipeline 入库竞争 | 前端上传的同时 CLI 也在入库 | 不冲突，各自创建独立条目 |

---

## 六、脚本操作与命令行（TC-RO-221 ~ TC-RO-260）

### 6.1 searev.py 命令行操作（TC-RO-221 ~ TC-RO-235）

| ID | 操作事件 | 命令 | 预期行为 |
|----|---------|------|---------|
| TC-RO-221 | 不带参数运行 searev.py | `python scripts/core/searev.py` | 显示帮助信息，不报错 |
| TC-RO-222 | event 搜索不带任何条件 | `python scripts/core/searev.py event` | 提示至少提供一个条件或返回全部 |
| TC-RO-223 | event 搜索使用非法的维度名 | `python scripts/core/searev.py event --moood 开心` | 报错提示无效参数 |
| TC-RO-224 | evaracter 搜索不带条件 | `python scripts/core/searev.py evaracter` | 返回全部人物或提示提供条件 |
| TC-RO-225 | text 搜索使用超长查询文本 | 输入 1000 字搜索文本 | 正常搜索或提示长度限制 |
| TC-RO-226 | searev.py 在 material.db 不存在时运行 | 数据库文件缺失 | 报错提示数据库不存在，建议运行 build_db.py |
| TC-RO-227 | searev.py 在 material.db 为空时运行 | 数据库存在但无数据 | 返回空结果 |
| TC-RO-228 | searev.py 结果输出 JSON 格式 | 使用 --format json 参数 | 输出合法 JSON |
| TC-RO-229 | searev.py 使用 --limit 0 | limit 设为 0 | 返回空或提示参数无效 |
| TC-RO-230 | searev.py 使用 --limit 负数 | `--limit -5` | 报错提示参数无效 |
| TC-RO-231 | searev.py 使用 --tension-min 和 --tension-max | 范围查询 | 返回范围内的事件 |
| TC-RO-232 | searev.py 使用 --tension-min > --tension-max | 无效范围 | 返回空或报错提示范围无效 |
| TC-RO-233 | 多次连续运行 searev.py | 快速运行多次搜索 | 每次都返回正确结果，无状态残留 |
| TC-RO-234 | 在错误的工作目录下运行 searev.py | 不在项目根目录运行 | 报错提示找不到数据库或自动定位 |
| TC-RO-235 | Python 版本不兼容时运行脚本 | 用 Python 3.8 运行需要 3.10+ 特性的脚本 | 明确的版本错误提示 |

### 6.2 build_db.py 操作（TC-RO-236 ~ TC-RO-245）

| ID | 操作事件 | 命令/操作 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-236 | data/novels/ 为空时运行 build_db.py | 没有任何小说 | 创建空数据库，不报错 |
| TC-RO-237 | 有事件 YAML 格式错误时运行 build_db.py | 某个 YAML 文件解析失败 | 跳过损坏文件继续处理，报告哪些文件有问题 |
| TC-RO-238 | build_db.py 运行过程中 Ctrl+C | 中断重建过程 | material.db 可能不完整，需重新运行 |
| TC-RO-239 | material.db 被其他进程锁定时运行 build_db.py | SQLite 写锁冲突 | 等待或报错提示数据库被占用 |
| TC-RO-240 | build_db.py 运行两次 | 连续运行两次 | 第二次覆盖第一次结果，无重复数据 |
| TC-RO-241 | build_db.py 处理含旧格式（嵌套）事件 | 新旧格式混合 | _flatten_event() 正确处理两种格式 |
| TC-RO-242 | build_db.py 处理超大数据量（10000+ 事件） | 多本大书 | 运行完成不超时，数据正确 |
| TC-RO-243 | 磁盘空间不足时 build_db.py | 空间不够创建 SQLite | 报错提示磁盘空间不足 |
| TC-RO-244 | build_db.py 处理 evaracters.yaml 格式变化 | 人物数据结构变更 | 兼容新旧格式，不丢失人物数据 |
| TC-RO-245 | build_db.py 后验证 SQLite 与 YAML 一致 | 查询 SQLite 与读取 YAML 对比 | 所有记录一一对应 |

### 6.3 validate_yaml.py 与 quality_audit.py（TC-RO-246 ~ TC-RO-260）

| ID | 操作事件 | 命令/操作 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-246 | validate_yaml 校验一个完全合规的事件 | 校验正确的 YAML | 通过校验，无错误报告 |
| TC-RO-247 | validate_yaml 校验缺少必填字段的事件 | 缺少 id 字段 | 报告缺失的必填字段名 |
| TC-RO-248 | validate_yaml 校验有非法标签值的事件 | `emotion: [绝望]` 但 tags.yaml 中没有 | 报告非法值和对应维度 |
| TC-RO-249 | validate_yaml 校验章节名不匹配的事件 | chapter 与 chapter_index 不一致 | 报告不匹配的 chapter 值 |
| TC-RO-250 | validate_yaml 校验空 events 目录 | 目录下无文件 | 提示无事件文件可校验 |
| TC-RO-251 | quality_audit 审计标签多样性正常的批次 | 审计第 1-10 章 | 审计通过，无告警 |
| TC-RO-252 | quality_audit 审计标签雷同的批次 | 10 个事件标签完全相同 | 报告雷同率和具体事件 ID |
| TC-RO-253 | quality_audit 审计 title 为编号形式 | `title: 事件1` | 报告使用了编号形式的 title |
| TC-RO-254 | quality_audit --batev 参数传了累积范围 | `--batev 1-200` 而非 `--batev 181-200` | 应该只审计 181-200 而非全部 |
| TC-RO-255 | quality_audit 批次范围超出实际事件数 | `--batev 301-320` 但只有 283 个事件 | 报告范围超出，只审计存在的事件 |
| TC-RO-256 | validate_yaml 遇到 YAML 解析失败的文件 | 文件语法错误 | 报告解析失败的文件名和原因 |
| TC-RO-257 | source_format.py 处理纯英文小说 | 非中文内容 | 跳过繁简转换，其他清洗正常 |
| TC-RO-258 | source_format.py 处理混合中英文小说 | 中英文夹杂 | 中文部分转换，英文部分保留 |
| TC-RO-259 | source_format.py 检测到缺章 | 章节编号不连续 | format_report 中标记缺章信息 |
| TC-RO-260 | build_event_index.py 处理嵌套和扁平混合 | 同一本书两种格式 | 全部正确索引 |

---

## 七、后端 API 异常（TC-RO-261 ~ TC-RO-290）

### 7.1 路由与参数（TC-RO-261 ~ TC-RO-275）

| ID | 操作事件 | 请求 | 预期响应 |
|----|---------|------|---------|
| TC-RO-261 | 访问不存在的 API 路径 | `GET /api/v1/nonexistent` | 404 Not Found |
| TC-RO-262 | 用 POST 访问只支持 GET 的端点 | `POST /api/v1/materials` | 405 Method Not Allowed |
| TC-RO-263 | 请求 material detail 用不存在的 ID | `GET /api/v1/materials/nm_fake_id` | 404 Not Found |
| TC-RO-264 | 搜索 API 传递非法 JSON body | `POST /api/v1/searev {invalid json}` | 422 Unprocessable Entity |
| TC-RO-265 | 搜索 API 传递空 body | `POST /api/v1/searev {}` | 返回空结果或提示条件缺失 |
| TC-RO-266 | API 请求头缺少 Content-Type | 缺少 application/json 头 | 正确处理或返回 415 |
| TC-RO-267 | API 请求超大 body（>1MB） | 发送超大 JSON | 拒绝请求，返回 413 |
| TC-RO-268 | 并发 100 个搜索请求 | 压力测试 | 全部正确响应，不崩溃 |
| TC-RO-269 | 后端启动但 material.db 被删 | 数据库不存在时处理请求 | 返回 503 或友好错误信息 |
| TC-RO-270 | 后端启动但 data/novels/ 不存在 | 目录缺失 | 返回空列表或友好提示 |
| TC-RO-271 | API 返回包含 NaN 或 Infinity 的 JSON | 统计数据出现非法数值 | 自动替换为 null 或 0，不返回非法 JSON |
| TC-RO-272 | 请求素材的 source.txt 内容（大文件） | `GET /api/v1/materials/{id}/source` | 流式传输或分页返回，不超时 |
| TC-RO-273 | 请求 stats.html（前端嵌入） | `GET /api/v1/materials/{id}/stats-html` | 返回 HTML 内容，Content-Type 正确 |
| TC-RO-274 | 请求标签字典 | `GET /api/v1/tags` | 返回完整的标签维度和值 |
| TC-RO-275 | 请求 pipeline 状态 | `GET /api/v1/pipeline/status` | 返回当前所有素材的 pipeline 进度 |

### 7.2 Pipeline API（TC-RO-276 ~ TC-RO-290）

| ID | 操作事件 | 请求/操作 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-276 | 通过 API 触发 pipeline 但素材不存在 | 指定不存在的 material_id | 返回 404 |
| TC-RO-277 | 通过 API 同时触发两个 pipeline | 并发请求 | 第二个请求被拒绝或排队 |
| TC-RO-278 | 通过 API 触发的 pipeline 中 LLM 配置无效 | API key 错误 | 返回配置错误信息 |
| TC-RO-279 | 通过 API 查询正在运行的 pipeline 进度 | 轮询进度端点 | 返回当前阶段和完成百分比 |
| TC-RO-280 | 通过 API 取消正在运行的 pipeline | 发送取消请求 | pipeline 安全停止，状态标记为已取消 |
| TC-RO-281 | API 请求 rebuild-db | `POST /api/v1/pipeline/rebuild-db` | 触发 build_db.py 重建 SQLite |
| TC-RO-282 | rebuild-db 执行过程中查询数据 | 重建中同时搜索 | 返回旧数据或提示正在重建 |
| TC-RO-283 | 后端接收到畸形的 material_id | `material_id: "../../etc/passwd"` | 路径遍历攻击被防御 |
| TC-RO-284 | 后端读取 YAML 文件时文件被另一进程修改 | 竞态条件 | 读取失败时返回 500 或重试 |
| TC-RO-285 | 后端 data_service 中路径拼接错误 | NOVELS_DIR 未正确初始化 | 清晰的启动错误日志 |
| TC-RO-286 | 后端 pipeline_service 无法找到 scripts 目录 | SCRIPTS_DIR 配置错误 | 启动时报错并给出修复建议 |
| TC-RO-287 | 后端返回的 YAML 文件包含中文 | 非 ASCII 内容 | JSON 序列化正确（ensure_ascii=False） |
| TC-RO-288 | 后端处理请求时内存不足 | 加载超大 YAML 文件 | 返回 500 而非进程崩溃 |
| TC-RO-289 | 后端日志级别设置为 DEBUG | 大量日志输出 | 不影响性能，日志可辅助排查问题 |
| TC-RO-290 | 后端在 Windows 系统上路径分隔符 | `\` vs `/` | Path 对象统一处理，不因平台差异失败 |

---

## 八、环境与依赖问题（TC-RO-291 ~ TC-RO-300）

| ID | 操作事件 | 触发方式 | 预期行为 |
|----|---------|---------|---------|
| TC-RO-291 | Python 环境缺少 yaml 包 | 没安装 pyyaml | import 失败，提示 `pip install pyyaml` |
| TC-RO-292 | Python 环境缺少 sqlite3 | 极少见但可能 | 清晰的导入错误提示 |
| TC-RO-293 | Node.js 版本不兼容前端构建 | Node 14 运行需要 18+ 的项目 | 构建失败，提示 Node 版本要求 |
| TC-RO-294 | npm install 失败（网络问题） | npm 依赖下载超时 | 提示重试或更换镜像源 |
| TC-RO-295 | 前端 build 后 dist/ 被误删 | 删了构建产物 | 重新 `npm run build` |
| TC-RO-296 | 后端依赖版本冲突 | fastapi 和 uvicorn 版本不兼容 | pip 报告冲突，提示解决方案 |
| TC-RO-297 | 在没有 git 的环境中运行 | 服务器没装 git | 系统正常运行，只是无法版本控制 |
| TC-RO-298 | 在只读文件系统上运行 | 如 Docker 只读挂载 | 写入操作明确失败并提示权限不足 |
| TC-RO-299 | macOS / Linux / Windows 跨平台路径差异 | 不同操作系统 | pathlib.Path 统一处理 |
| TC-RO-300 | 项目目录被移动到不同位置 | 从 ~/proj/ 移到 /opt/proj/ | 相对路径正常工作，绝对路径配置需更新 |
