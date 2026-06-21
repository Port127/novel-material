# Agent 与 Claude Skills 同步设计

## 目标

以 `.agents/skills` 为项目 Skills 的唯一事实来源，使 `.claude/skills` 保持可重复生成的镜像，避免不同 Agent 获得过期或互相矛盾的项目能力说明。

## 当前问题

两个目录包含相同的 12 个 Skill，但以下 4 个文件内容不同：

- `nm-search`：Claude 侧缺少七类质量优先检索、JSON 输出和降级语义。
- `my-create-skill`、`plan-first`、`skill-discovery`：内容包含平台名称或目录差异；Codex 侧还误用了 `.Codex` 大写路径。

`.claude/skills/.DS_Store` 不属于 Skill 内容，不参与同步和校验。

## 设计

### 事实来源

- `.agents/skills` 是唯一可直接编辑的共享源。
- `.claude/skills` 由同步脚本更新，不单独维护业务内容。

### 平台中立化

不维护 Claude/Codex 两套正文，也不使用替换白名单。存在平台差异的 Skill 改为平台中立说明：

- 同时列出 `.agents/skills`、`.claude/skills`、`~/.codex/skills` 和 `~/.claude/skills` 等真实路径。
- 将“Codex/Claude Code 内置机制”改为“宿主工具内置机制”。
- 扫描会话或 Skill 时明确列出各平台来源，由执行 Agent 选择自身可用路径。

完成后，两边所有受管文件应逐字一致。

### 同步工具

新增脚本提供两种模式：

- 默认同步：从 `.agents/skills` 复制受管文件到 `.claude/skills`，创建缺失目录并更新漂移文件。
- `--check`：只检查，不写文件；发现缺失、多余或内容不同则返回非零退出码。

同步范围包括每个 Skill 目录下的 `SKILL.md` 和辅助脚本/资源；忽略 `.DS_Store`、缓存和临时文件。脚本不得反向覆盖 `.agents/skills`。

## 安全与错误处理

- 同步前校验源目录存在。
- 只删除目标目录中属于受管 Skill、但源侧已不存在的文件；不处理隐藏文件和未识别的目标文件。
- 文件复制失败时返回非零退出码并列出路径。
- 脚本不访问网络，不修改用户素材、配置或数据库。

## 验证

- 先证明当前 `--check` 因 4 个漂移 Skill 失败。
- 同步后 `--check` 返回成功。
- 校验两边 Skill 名称集合、受管相对路径和内容哈希一致。
- 运行现有全量测试，确认同步工具和文档修改不影响项目行为。

## 交付

- 平台中立化后的 3 个 Skill。
- 同步后的 `nm-search` 及全部 `.claude/skills` 镜像。
- 可重复运行的同步/校验脚本与自动化测试。
- 在 `AGENTS.md` 中记录事实来源和禁止直接编辑镜像的规则。
