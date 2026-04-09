# 知乎调研测试案例（100 例）

> 基于知乎 20+ 篇小说素材库管理、标签体系、搜索检索、AI 辅助创作、数据安全等相关文章调研，
> 结合 novel-material 系统实际功能设计。

## 参考资料来源

| # | 文章/话题 | 知乎链接 | 关联维度 |
|---|----------|---------|---------|
| 1 | 你不是文笔差，只是缺个素材库！保姆级素材收集整理教程 | zhuanlan.zhihu.com/p/681213333 | 素材库搭建 |
| 2 | 如何在阅读中收集整理写作素材 | zhuanlan.zhihu.com/p/54957669 | 素材整理 |
| 3 | 请问你是如何积累写作素材的？ | zhihu.com/question/24094368 | 素材积累 |
| 4 | 高效查找小说素材的几个小技巧 | zhuanlan.zhihu.com/p/941071924 | 检索效率 |
| 5 | 如何积累和分类整理写作素材？ | zhihu.com/question/28024403 | 分类方法 |
| 6 | 网络小说标签体系构建 | zhuanlan.zhihu.com/p/422902283 | 标签设计 |
| 7 | 多标签分类及其基本做法 | zhuanlan.zhihu.com/p/570797393 | 多维标签 |
| 8 | 深度解析文本分类与标签的应用价值和原理 | zhuanlan.zhihu.com/p/260575592 | 标签原理 |
| 9 | 你们的笔记、标签、分类是怎样的？ | zhihu.com/question/20256448 | 分类实践 |
| 10 | 如何正确地拆书 | zhuanlan.zhihu.com/p/351328097 | 场景拆解 |
| 11 | 雪花写作法 | zhuanlan.zhihu.com/p/2001646363016983889 | 故事结构 |
| 12 | 网文写作：拆书拆什么？如何拆？ | zhuanlan.zhihu.com/p/673645624 | 拆书方法 |
| 13 | 小说写作丨怎样的人物设定技巧 | zhuanlan.zhihu.com/p/295612214 | 人物设定 |
| 14 | 角色设定怎么做？搭建「人物宝典」的详细教程分享 | zhuanlan.zhihu.com/p/653190295 | 角色管理 |
| 15 | 人物关系图如何架构——写作笔记 | zhuanlan.zhihu.com/p/8111159483 | 人物关系 |
| 16 | 全文检索的索引设计 | zhuanlan.zhihu.com/p/520001238 | 索引设计 |
| 17 | 搜索引擎都在用的倒排索引——原理与实现 | zhuanlan.zhihu.com/p/324378430 | 倒排索引 |
| 18 | SQLite数据备份 | zhuanlan.zhihu.com/p/111112545 | 数据库备份 |
| 19 | 深入解析 YAML 配置文件：从语法到最佳实践 | zhuanlan.zhihu.com/p/644393484 | YAML 管理 |
| 20 | 如何处理好前后端分离的 API 问题 | zhuanlan.zhihu.com/p/26385106 | 前后端交互 |
| 21 | 用 Git 帮助写作者更好地完成工作 | zhuanlan.zhihu.com/p/88492519 | 版本控制 |
| 22 | 如何理解 GitHub+Markdown 轻量级结构化写作方案 | zhuanlan.zhihu.com/p/658428527 | 结构化写作 |
| 23 | 基于 notion 谈个人图书管理的多维度视角 | zhuanlan.zhihu.com/p/170615564 | 多维管理 |
| 24 | 基于大模型的海量标签多分类方法 | zhuanlan.zhihu.com/p/911108003 | AI标签分类 |
| 25 | AI 失控误删文件？超实用文件恢复软件来了 | zhuanlan.zhihu.com/p/2014393214891753895 | AI误操作 |

---

## 调研总结：知乎用户痛点 → 测试维度

| 痛点 | 来源 | 对应测试维度 |
|------|------|-------------|
| 素材分类过多导致认知负担重，找不到东西 | #1 #5 #9 | 标签检索效率 |
| 标签体系过于僵化或过于松散，标签值泛滥 | #6 #7 #8 | 标签合法性校验 |
| 搜索不准确——关键词匹配不到想要的素材 | #4 #16 #17 | 多维检索准确率 |
| 人物众多时设定遗忘、关系混乱 | #13 #14 #15 | 人物数据完整性 |
| 长篇小说拆分时场景遗漏、标签雷同 | #10 #11 #12 | 场景质量审计 |
| YAML 格式出错导致解析失败 | #19 | YAML 格式校验 |
| SQLite 数据丢失无法恢复 | #18 | 数据一致性 |
| AI 自动标注标签千篇一律 | #24 #25 | Anti-Pattern 检测 |
| 前后端 API 异常时用户无反馈 | #20 | 错误提示 |
| 多人协作 / 版本控制丢失历史 | #21 #22 | 数据持久化 |

---

## A. 素材库管理与入库（TC-ZH-001 ~ TC-ZH-015）

| ID | 测试案例 | 预期结果 | 来源痛点 |
|----|---------|---------|---------|
| TC-ZH-001 | 入库一本 500 字的短篇小说 | 成功创建 meta.yaml 和 source.txt，status=raw | 素材入库基本流程 |
| TC-ZH-002 | 入库一本 300 万字的超长网文 | 成功入库，source.txt 完整不截断，耗时可接受 | 大文件处理 |
| TC-ZH-003 | 入库一本繁体中文小说 | source-format 正确转换为简体，format_report 记录转换数量 | 格式清洗 |
| TC-ZH-004 | 入库一本含大量广告/推广链接的小说 | source-format 清除广告段落，format_report 中标记清除数量 | 格式清洗 |
| TC-ZH-005 | 入库文件路径包含中文和空格 | 正常入库，不因路径特殊字符失败 | 路径兼容 |
| TC-ZH-006 | 同一本小说重复入库 | 系统检测到重复并提示，不创建重复条目 | 去重 |
| TC-ZH-007 | 入库空文件（0 字节） | 拒绝入库并给出明确错误提示 | 异常输入 |
| TC-ZH-008 | 入库非 txt 格式文件（如 .docx、.pdf） | 要么成功转换，要么拒绝并提示格式不支持 | 格式兼容 |
| TC-ZH-009 | 入库后检查 index.yaml 是否更新 | index.yaml 新增一条 material 记录，字段完整 | 注册完整性 |
| TC-ZH-010 | 入库编码为 GBK 的文件 | 成功识别并转换编码，或明确提示编码问题 | 编码处理 |
| TC-ZH-011 | material-import 导入外部已分析素材 | 重新生成 material_id，校验标签合法性，注册到 index.yaml | 导入流程 |
| TC-ZH-012 | material-import 导入包含非法标签值的素材 | 检测到非法标签并报错，不静默入库 | 标签校验 |
| TC-ZH-013 | material-import 导入缺少 meta.yaml 的文件夹 | 明确报错，提示缺少必要文件 | 导入校验 |
| TC-ZH-014 | material-import 导入已存在的同名小说 | 检查去重逻辑，不覆盖现有数据 | 去重保护 |
| TC-ZH-015 | 连续入库 10 本小说，检查 index.yaml 一致性 | 所有 10 本都正确注册，ID 无重复 | 批量入库 |

## B. 标签体系与分类（TC-ZH-016 ~ TC-ZH-030）

| ID | 测试案例 | 预期结果 | 来源痛点 |
|----|---------|---------|---------|
| TC-ZH-016 | 检查 tags.yaml 所有 20 个场景标签维度是否齐全 | 确认 scene_type/conflict/stakes 等 20 维全部存在 | 标签完整性 |
| TC-ZH-017 | 检查 tags.yaml 所有 7 个小说标签维度是否齐全 | 确认 genre/tone/narrative_structure 等 7 维全部存在 | 标签完整性 |
| TC-ZH-018 | 向 tags.yaml 添加新标签值（tag-add） | 新值出现在对应维度下，YAML 格式正确 | 标签扩展 |
| TC-ZH-019 | 添加一个已存在的重复标签值 | 拒绝添加并提示已存在 | 标签去重 |
| TC-ZH-020 | 合并两个同义标签（tag-merge） | 旧标签值在全局被替换为新值，全部场景 YAML 更新 | 标签归并 |
| TC-ZH-021 | 场景 YAML 中使用了 tags.yaml 中不存在的标签值 | validate_yaml.py 校验报错，明确指出非法值 | 标签合法性 |
| TC-ZH-022 | 场景 YAML 中某个必填标签字段为空 | validate_yaml.py 校验报错，指出缺失字段 | 必填校验 |
| TC-ZH-023 | 场景中 tension 值超出 1-5 范围（如 0 或 6） | 校验报错，提示 tension 必须在 1-5 之间 | 范围校验 |
| TC-ZH-024 | 标签维度大小写不一致（如 Scene_Type 替代 scene_type） | 校验报错或自动纠正 | 大小写敏感 |
| TC-ZH-025 | 标签值含前后空格（如 " 对决 "） | 校验检测到空格并报错或自动 trim | 空格处理 |
| TC-ZH-026 | 同一场景的 scene_type 标签列表含重复值 | 校验检测到重复并报告 | 值重复 |
| TC-ZH-027 | 小说级标签（novel-tags）覆盖所有 7 个维度 | 生成的 tags.yaml 7 个维度都有值 | 覆盖率 |
| TC-ZH-028 | tags.yaml 中删除一个正在使用中的标签值 | 系统应阻止或提示该值仍在使用 | 安全删除 |
| TC-ZH-029 | 多维标签组合检索：scene_type=对决 AND emotion=燃 | 返回同时满足两个条件的场景 | 组合检索 |
| TC-ZH-030 | 检查整本书场景标签多样性——不能所有场景标签相同 | quality_audit 检测出标签雷同并告警 | Anti-Pattern |

## C. 搜索与检索（TC-ZH-031 ~ TC-ZH-050）

| ID | 测试案例 | 预期结果 | 来源痛点 |
|----|---------|---------|---------|
| TC-ZH-031 | 关键词检索"告别" | 返回包含"告别"的素材，按相关度排序 | 基本搜索 |
| TC-ZH-032 | 关键词检索一个不存在的词（如"飞天遁地炸裂锤"） | 返回空结果集，不报错 | 空结果处理 |
| TC-ZH-033 | 搜索中文标点符号（如"——"破折号） | 正确处理，不因标点导致搜索引擎报错 | 特殊字符 |
| TC-ZH-034 | scene 搜索：按 emotion=悲伤 筛选 | 返回所有 emotion 含"悲伤"的场景 | 单维搜索 |
| TC-ZH-035 | scene 搜索：按 emotion=悲伤 AND interaction=告别 | 仅返回同时满足两个条件的场景 | 多维 AND |
| TC-ZH-036 | scene 搜索：标签多选（OR 查询）emotion=燃 OR emotion=紧张 | 返回含"燃"或"紧张"的所有场景 | 多选 OR |
| TC-ZH-037 | scene 搜索：按 tension-min=4 过滤高张力场景 | 仅返回 tension>=4 的场景 | 数值过滤 |
| TC-ZH-038 | character 搜索：按 archetype=导师 | 返回所有原型为"导师"的人物 | 人物搜索 |
| TC-ZH-039 | character 搜索：按角色名"张三"搜索 | 返回张三出现的所有场景 | 人物-场景 |
| TC-ZH-040 | text 全文搜索：在 source.txt 中搜索一段原文 | 返回包含该段文字的素材 | 全文搜索 |
| TC-ZH-041 | 跨小说搜索：同一标签条件在多本小说中检索 | 返回来自不同小说的场景，标明出处 | 跨素材检索 |
| TC-ZH-042 | 上下文检索：输入"男主雨中追女主"的写作上下文 | 返回相关场景+人物+技法参考 | 语义检索 |
| TC-ZH-043 | 搜索结果分页：limit=10，验证分页正确性 | 返回 10 条结果，支持翻页 | 分页 |
| TC-ZH-044 | 搜索 SQL 注入测试：输入 `'; DROP TABLE scenes; --` | 不执行注入，正常返回空结果或报错 | 安全 |
| TC-ZH-045 | SQLite 和 YAML 搜索结果一致性对比 | 两种方式返回的场景集合相同 | 数据一致性 |
| TC-ZH-046 | 新入库的小说在 build-index 前能否被搜索到 | 不能，需先 build-index 才能通过 SQLite 检索 | 索引时效 |
| TC-ZH-047 | build-index 后立即搜索刚入库的场景 | 能搜索到新入库的场景 | 索引更新 |
| TC-ZH-048 | 在前端 SceneSearch 页面执行多标签搜索 | 前端正确发送请求，后端正确返回，卡片正确渲染 | 前端集成 |
| TC-ZH-049 | 在前端 CharacterSearch 页面搜索人物 | 返回结构化人物卡片（角色/原型/弧线/心理） | 前端展示 |
| TC-ZH-050 | 搜索响应时间：1000+ 场景库中搜索不超过 2 秒 | 响应时间 < 2s | 性能 |

## D. 场景拆分与质量（TC-ZH-051 ~ TC-ZH-065）

| ID | 测试案例 | 预期结果 | 来源痛点 |
|----|---------|---------|---------|
| TC-ZH-051 | novel-scenes 拆分一批 10 章内容 | 生成对应数量的场景 YAML，每个文件格式合规 | 基本拆分 |
| TC-ZH-052 | 场景 title 不能是"场景1""场景2"的编号形式 | 所有 title 都是有语义的概括短语 | Anti-Pattern |
| TC-ZH-053 | 场景 summary 不能是章节开头几十字的截断 | summary 是对核心事件的概括，而非首句复制 | Anti-Pattern |
| TC-ZH-054 | 同一批次内场景标签组合不能完全相同 | 任意两个场景的标签组合有差异 | Anti-Pattern |
| TC-ZH-055 | 场景 chapter 字段从 chapter_index.yaml 逐字拷贝 | chapter 值与 chapter_index.yaml 完全一致 | 字段准确性 |
| TC-ZH-056 | 场景 YAML 含中文引号的字符串用单引号包裹 | YAML 能被 safe_load 正确解析 | YAML 安全 |
| TC-ZH-057 | 全书自动模式（all）不需逐批确认 | 自动循环分批执行，无需用户干预 | 自动化 |
| TC-ZH-058 | 每批场景写入后运行 quality_audit 审计 | 审计通过或报告问题，审计范围仅为本批 | 质量审计 |
| TC-ZH-059 | quality_audit 检测到标签雷同批次 | 报告雷同比例，提示需要重做 | 质量门控 |
| TC-ZH-060 | 场景 text_range 与 source.txt 行号范围对应 | 根据 text_range 取出的文本与场景内容匹配 | 行号准确 |
| TC-ZH-061 | 300+ 章小说的场景拆分进度追踪 | meta.yaml 中 pipeline 进度字段实时更新 | 进度追踪 |
| TC-ZH-062 | 场景拆分中断后恢复（continue 模式） | 从上次中断的批次继续，不重复已完成的批次 | 断点恢复 |
| TC-ZH-063 | 跨对话恢复场景拆分 | 新对话能读取 meta.yaml 中的进度，自动定位恢复点 | 跨对话 |
| TC-ZH-064 | 验证场景 ID 格式 ch{NNNN}_s{NN} | 所有 ID 符合命名规范 | ID 规范 |
| TC-ZH-065 | 验证 conflict=[] 不是所有场景都为空 | 大部分场景有具体冲突类型 | 质量 |

## E. 人物与世界观（TC-ZH-066 ~ TC-ZH-075）

| ID | 测试案例 | 预期结果 | 来源痛点 |
|----|---------|---------|---------|
| TC-ZH-066 | novel-characters 生成人物名册 | characters.yaml 包含 roster 列表，每个人物有 name/role | 人物生成 |
| TC-ZH-067 | 人物有完整的心理维度（fatal_flaw/obsession/soft_spot/misbelief） | roster 中主要角色的心理字段不为空 | 心理深度 |
| TC-ZH-068 | 人物关系网包含双向关系 | A→B 和 B→A 的关系都有记录 | 关系完整性 |
| TC-ZH-069 | 人物弧线 arc_summary 不是泛泛的"成长" | 弧线描述具体到事件或变化节点 | 弧线质量 |
| TC-ZH-070 | novel-worldbuilding 生成世界观设定 | worldbuilding.yaml 包含力量体系/地理/势力/背景 | 世界观生成 |
| TC-ZH-071 | novel-outline 大纲覆盖全书结构 | outline.yaml 包含 premise/theme/structure | 大纲完整 |
| TC-ZH-072 | refine 后大纲补充伏笔网络 | 精调后 outline.yaml 出现 plot_threads 等新字段 | 精调增量 |
| TC-ZH-073 | refine 后人物弧线更精确 | 精调后 arc_summary 包含具体章节引用 | 精调质量 |
| TC-ZH-074 | character_index.yaml 聚合了所有小说的人物 | 多本小说的人物都出现在全局索引中 | 全局聚合 |
| TC-ZH-075 | plot_index.yaml 聚合了所有小说的剧情 | 多本小说的剧情线索都出现在全局索引中 | 全局聚合 |

## F. 索引与数据库（TC-ZH-076 ~ TC-ZH-085）

| ID | 测试案例 | 预期结果 | 来源痛点 |
|----|---------|---------|---------|
| TC-ZH-076 | build-index 生成 scenes_index.yaml（倒排索引） | 索引文件包含标签→场景ID的映射 | 索引生成 |
| TC-ZH-077 | build-index 生成 scenes_manifest.yaml（场景清单） | 清单文件包含所有场景的压缩视图 | 清单生成 |
| TC-ZH-078 | build-index 同时更新 SQLite | material.db 中 scenes 表记录数与场景文件数一致 | SQLite 同步 |
| TC-ZH-079 | 从 YAML 完整重建 SQLite（build_db.py） | 重建后搜索结果与之前一致 | 可重建性 |
| TC-ZH-080 | 删除 material.db 后重建 | 重建成功，无数据丢失 | 派生层可恢复 |
| TC-ZH-081 | 新旧格式场景 YAML 混合时 build_db.py 兼容 | 嵌套格式和扁平格式都能正确入库 | 格式兼容 |
| TC-ZH-082 | SQLite 中场景记录与 YAML 文件一一对应 | 无多余记录，无遗漏记录 | 数据一致 |
| TC-ZH-083 | 索引统计数据与实际场景数吻合 | stats.yaml 中 total_scenes 等于场景文件数 | 统计准确 |
| TC-ZH-084 | index.yaml 中所有 folder 路径都实际存在 | 每个注册路径都能访问到对应文件夹 | 路径有效 |
| TC-ZH-085 | 多本小说同时 build-index 后全局索引不冲突 | plot_index 和 character_index 正确合并 | 并发安全 |

## G. 前端展示与交互（TC-ZH-086 ~ TC-ZH-095）

| ID | 测试案例 | 预期结果 | 来源痛点 |
|----|---------|---------|---------|
| TC-ZH-086 | Dashboard 页面加载素材库概览 | 显示素材总数、场景总数、标签覆盖率等指标 | 首页概览 |
| TC-ZH-087 | MaterialList 列表页显示所有已入库素材 | 列出所有小说，含书名/作者/状态 | 素材列表 |
| TC-ZH-088 | MaterialDetail 详情页各 Tab 正确加载 | 大纲/世界观/人物/标签/统计 Tab 都能渲染 | 详情展示 |
| TC-ZH-089 | MaterialDetail 遇到缺失字段不崩溃 | 字段不存在时用 RemainingFields 兜底渲染 | 容错 |
| TC-ZH-090 | SceneSearch 结果卡片结构化展示 | 显示标题/张力/摘要/标签/人物，不是 JSON | 卡片渲染 |
| TC-ZH-091 | CharacterSearch 人物卡片结构化展示 | 显示角色/原型/弧线/心理，不是 JSON | 卡片渲染 |
| TC-ZH-092 | TagDictionary 页面显示完整标签字典 | 所有维度和值都能浏览 | 标签浏览 |
| TC-ZH-093 | Settings 页面能正常加载和保存配置 | 配置修改后持久化生效 | 设置持久化 |
| TC-ZH-094 | 后端 API 返回 500 时前端显示友好错误提示 | 不显示白屏或原始堆栈 | 错误处理 |
| TC-ZH-095 | 后端 API 响应超时时前端显示加载提示 | 有 loading 状态，超时后提示重试 | 超时处理 |

## H. 统计与报告（TC-ZH-096 ~ TC-ZH-100）

| ID | 测试案例 | 预期结果 | 来源痛点 |
|----|---------|---------|---------|
| TC-ZH-096 | novel-stats 生成 stats.yaml | 包含情节/转折/节奏/伏笔/人物等统计数据 | 统计生成 |
| TC-ZH-097 | novel-stats 生成 stats.md | Mermaid 图表语法正确，可渲染 | Markdown 报告 |
| TC-ZH-098 | novel-stats 生成 stats.html | HTML 可在浏览器打开，ECharts 图表正常显示 | 交互报告 |
| TC-ZH-099 | stats 中不含编造的质量数据 | 无信号时写 TBD 而非胡编数字 | 数据真实性 |
| TC-ZH-100 | 前端能加载并展示 stats.html 的内容 | 详情页统计 Tab 正确嵌入交互报告 | 前端集成 |
