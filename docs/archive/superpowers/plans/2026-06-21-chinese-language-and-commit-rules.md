# 中文沟通与 Git 提交规则实施计划

> **供执行 Agent 使用：** 必须使用 `executing-plans` 逐项执行本计划。步骤使用复选框（`- [ ]`）跟踪。

**目标：** 在 Codex 全局范围和 Novel Material 项目范围内同时建立中文沟通及详细中文 Git 提交规范。

**架构：** 使用 Codex 官方支持的两级 `AGENTS.md` 指令链。`~/.codex/AGENTS.md` 提供所有项目继承的默认规则，仓库根目录 `AGENTS.md` 再次声明项目约束；项目规则与全局规则保持一致，不修改运行配置。

**技术栈：** Markdown、Codex `AGENTS.md` 指令发现机制、Git。

---

## 文件职责

- 新建 `~/.codex/AGENTS.md`：保存当前用户所有 Codex 项目的默认语言与提交规范。
- 修改 `AGENTS.md`：保存 Novel Material 仓库内可独立继承的语言与提交规范。
- 保留 `docs/superpowers/specs/2026-06-21-chinese-language-and-commit-rules-design.md`：记录已经确认的设计依据。
- 新建 `docs/superpowers/plans/2026-06-21-chinese-language-and-commit-rules.md`：记录本次实施与验证步骤。

### 任务一：增加项目级规则

**文件：**
- 修改：`AGENTS.md`

- [x] **步骤一：在“相关文档”之后增加规则章节**

写入以下内容：

````markdown
## 语言与沟通规范

- 所有面向用户的回复、计划、任务说明、进度更新、分析结论、决策依据、错误说明和新编写的说明性文档默认使用简体中文。
- 内部隐藏推理不会展示；所有对用户可见的推理摘要和判断依据必须使用中文。
- 命令、代码、路径、配置键、字段名、API 名称、模型名称和无法准确翻译的专有名词可以保留原文。
- 用户明确要求使用其他语言时，以用户当前请求为准。

## Git 提交规范

- 提交标题使用 `<type>(<scope>): <中文摘要>`；`scope` 可省略。
- `type` 沿用项目已有的 `feat`、`fix`、`refactor`、`docs`、`test`、`chore`、`skills` 等英文类型。
- 除类型、作用域、代码标识、文件名、命令和技术专名外，提交标题与正文必须使用中文。
- 每次提交必须包含正文，禁止只有标题。
- 正文必须包含“主要改动”和“验证结果”；“背景与目的”“影响范围”根据实际情况填写。
- “主要改动”必须列出具体内容点，不使用“更新代码”“修复问题”等无法审计的笼统描述。
- “验证结果”必须记录执行的测试或检查及其结果；未运行测试时必须明确说明原因。

推荐格式：

```text
docs(agents): 增加中文沟通与提交规范

背景与目的：
- 统一所有 Codex 项目的中文协作习惯

主要改动：
- 增加面向用户内容默认使用简体中文的要求
- 增加提交标题、详细正文和验证记录规范

影响范围：
- 只影响 Agent 沟通与 Git 提交格式，不改变项目运行行为

验证结果：
- 检查项目与全局 AGENTS.md，规则内容完整
- 执行 Git 差异格式检查，未发现空白错误
```
````

- [x] **步骤二：检查项目规则**

执行：

```bash
rg -n "语言与沟通规范|Git 提交规范|主要改动|验证结果" AGENTS.md
git diff --check -- AGENTS.md
```

预期：两组规则及两个强制正文栏目均可检索到，Git 差异没有空白错误。

### 任务二：增加全局规则

**文件：**
- 新建：`~/.codex/AGENTS.md`

- [x] **步骤一：确认不存在优先级更高的全局覆盖文件**

执行：

```bash
test ! -s ~/.codex/AGENTS.override.md
```

预期：退出码为 0；不存在非空 `AGENTS.override.md` 抢先覆盖全局规则。

- [x] **步骤二：创建全局规则文件**

文件内容与任务一的“语言与沟通规范”和“Git 提交规范”保持一致，并在开头增加：

```markdown
# Codex 全局 Agent 规则

本文件适用于当前用户的所有 Codex 项目。项目内更具体的 `AGENTS.md` 可以补充规则，但不得无故降低以下中文沟通与提交要求。
```

- [x] **步骤三：检查全局规则**

执行：

```bash
test -s ~/.codex/AGENTS.md
rg -n "语言与沟通规范|Git 提交规范|主要改动|验证结果" ~/.codex/AGENTS.md
```

预期：文件非空，规则标题与强制正文栏目均可检索到。

### 任务三：整体验证与项目提交

**文件：**
- 修改：`AGENTS.md`
- 新建：`docs/superpowers/plans/2026-06-21-chinese-language-and-commit-rules.md`

- [x] **步骤一：核对工作区边界**

执行：

```bash
git status --short
git diff -- config/providers.yaml docs/feedback.md
```

预期：用户原有的 `config/providers.yaml`、`docs/feedback.md` 修改仍然保留，本次没有覆盖两者。

- [x] **步骤二：提交项目规则与实施计划**

```bash
git add AGENTS.md docs/superpowers/plans/2026-06-21-chinese-language-and-commit-rules.md
git commit -m "docs: 增加全局与项目中文协作规则" \
  -m "主要改动：" \
  -m "- 在项目 AGENTS.md 中增加中文沟通与可见推理摘要规范" \
  -m "- 明确 Git 提交必须使用中文摘要和详细正文" \
  -m "- 增加规则实施计划和可复查的验证步骤" \
  -m "影响范围：" \
  -m "- 全局规则影响当前用户后续新建的 Codex 会话" \
  -m "- 项目规则影响 Novel Material 仓库内的 Agent 协作" \
  -m "验证结果：" \
  -m "- 项目与全局规则文件内容检查通过" \
  -m "- Git 差异格式检查通过，用户原有工作区修改未被覆盖"
```

预期：只提交 `AGENTS.md` 和本实施计划；`~/.codex/AGENTS.md` 位于仓库外，不进入 Git。

- [x] **步骤三：说明重新加载要求**

当前会话继续主动遵守新规则。告知用户：Codex 在新会话启动时重新构建全局与项目指令链，因此新建会话后可完整验证自动加载效果。
