# Core Beliefs

Novel Material 系统的核心设计原则。

## 仓库即记录系统

所有素材、索引、标签存储在版本化仓库内。
Agent 运行时无需外部依赖（聊天记录、Google Docs 等）。

优先使用 YAML 格式：
- 便于 Agent grep、diff、PR 更新
- 结构化，易于验证
- 人类可读，便于调试

## Skills 作为唯一入口

9 个活跃 skills 封装所有操作逻辑：
- 用户不直接操作 YAML 文件
- Skills 保证操作一致性和验证
- Skills 提供清晰的输入输出契约

反模式：让用户手动编辑 index.yaml

## 渐进披露

Layer 1：Skill 元数据（`SKILL.md` frontmatter）— 快速判断用途
Layer 2：`AGENTS.md` — 路由导航（≤100行）
Layer 3：`docs/` — 设计、产品、计划详情
Layer 4：`data/` — 素材存储

Agent 从小开始，跟随链接而非一次性加载所有内容。

## ID 规范保证唯一性

`nm_{type}_{YYYYMMDD}_{random4}` 格式：
- 跨项目唯一
- 时间追溯
- 类型识别

反模式：使用简单数字 ID 或无规范命名

## 标签规范化

6 层 19 维标签体系：
- 定义在 `data/tags.yaml`
- 场景级标签内嵌在 scenes/*.yaml
- 小说级标签在 tags.yaml
- 合并同义标签使用 `tag-merge`

反模式：保留混乱的原始标签

## 索引分层

全局索引 + 小说级数据：
- 全局索引为汇总视图（自动生成）
- 每部小说独立文件夹自治
- 上层索引引用下层索引

反模式：单一巨型索引文件

## 质量追踪

`docs/QUALITY_SCORE.md` 评分卡：
- 不编造数据（无信号写 TBD）
- 评分维度明确
- 改进计划可追溯

反模式：编造覆盖率百分比

## Related Docs

- [../DESIGN.md](../DESIGN.md)
- [../../AGENTS.md](../../AGENTS.md)