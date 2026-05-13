---
name: git-commit-push
description: >-
  标准化 Git 工作流：检查状态、commit、可选 push。区分当前对话修改与全部变更。仅当用户明确说出"使用 git-commit-push"或"启动 git-commit-push"时触发。不适用于任何隐式场景。
---

# Git 工作流

标准化 Git 工作流，区分 commit/push 和 当前/全部 变更范围。

## 触发约束

此 skill **仅通过显式调用触发**。

### ⛔ 不触发的场景
- 用户提到"commit"、"push"、"git"等但未提及 git-commit-push
- 用户说"帮我commit"（这是日常指令，不触发本 skill）
- 用户未显式引用 @git-commit-push

### ✅ 触发条件
必须同时满足：
1. 用户明确说出"使用 git-commit-push"或"启动 git-commit-push"，或显式引用 @git-commit-push
2. 用户提供了明确需求或上下文

---

## 问题

用户反复要求 Git 操作（agent transcripts 中 17 次相关请求），且场景多样：

- 只 commit，不 push
- commit then push
- 只 commit 当前对话修改的文件
- commit 所有变更

如果 agent 混淆场景，会：
- 用户没说 push 却自动 push 了
- 用户只想 commit 当前修改，却被 commit 了所有未提交文件
- 提交了用户未确认的敏感文件

## 核心原则

### 默认行为

| 参数 | 默认值 | 触发条件 |
|------|--------|---------|
| push | 不 push | 用户明确说"push"才执行 |
| commit 范围 | 当前对话修改 | 用户明确说"全部"或"所有变更"才 commit 所有 |

### 场景矩阵

| 用户指令 | commit 范围 | 是否 push |
|---------|------------|----------|
| "帮我commit" | 当前对话修改 | 不 push |
| "commit then push" | 当前对话修改 | push |
| "commit 所有变更" | 所有变更 | 不 push |
| "commit 所有，然后push" | 所有变更 | push |
| "检查git，帮我commit" | 当前对话修改 | 不 push |

## 执行流程

### Step 1: 检查 Git 状态

运行并展示：

```bash
git status
git diff --stat
```

输出中区分：
- **当前对话修改**：agent 使用 Edit/Write/Bash 创建/修改/删除的文件
- **其他变更**：用户手动修改、其他工具产生的变更

### Step 2: 确认范围

根据用户指令确定范围：

| 用户指令 | 操作 |
|---------|------|
| 未指定范围（如"帮我commit"） | 只 commit 当前对话修改 |
| "全部" / "所有变更" | commit 所有未提交文件 |
| 有歧义 | 询问用户确认 |

### Step 3: 展示即将提交的文件

列出即将提交的文件：

```markdown
## 即将提交

**范围**: {当前对话修改 / 所有变更}

| 文件 | 状态 | 来源 |
|------|------|------|
| `path/to/file.py` | modified | agent Edit |
| `path/to/another.py` | new file | agent Write |
| `path/to/config.json` | modified | 用户手动修改 |

**敏感文件检查**:
- ✅ 无 .env、credentials 等敏感文件
- ⚠️ 发现敏感文件: {文件列表} — 需用户确认是否提交
```

### Step 4: 执行 commit

生成 commit message：

- 基于变更内容生成（非机械总结）
- 格式：`{type}({scope}): {brief description}`
- type: feat/fix/refactor/docs/test/chore

执行 commit：

```bash
git add {文件列表}
git commit -m "..."
```

### Step 5: 执行 push（可选）

**默认不 push。**

用户明确说"push"时才执行：

```bash
git push origin {当前分支}
```

push 前展示目标分支，确认无误。

## 如何识别"当前对话修改的文件"

| 来源 | 标记 |
|------|------|
| agent 使用 Edit 工具修改的文件 | 记录为当前修改 |
| agent 使用 Write 工具创建的文件 | 记录为当前修改 |
| agent 使用 Bash 创建/删除的文件 | 记录为当前修改 |
| 用户手动编辑的文件 | 不属于当前对话修改 |
| 其他工具（如 IDE）产生的变更 | 不属于当前对话修改 |

实际操作：agent 在对话中追踪自己操作的文件路径，commit 时只 add 这些文件。

## 反模式

| 反模式 | 正确做法 |
|--------|---------|
| 默认 push | 用户明确说"push"才 push |
| 默认 commit 所有变更 | 用户明确说"全部"才 commit 所有 |
| 跳过状态检查 | 必须先展示 git status |
| commit 用户未确认的敏感文件 | 发现敏感文件需询问 |
| commit message 与变更不符 | 基于实际变更生成 |

## 完成检查清单

标记 Git 操作完成前确认：
- [ ] git status 已运行并展示
- [ ] commit 范围已确认（当前修改 / 所有变更）
- [ ] 即将提交的文件已展示
- [ ] 敏感文件已检查（如有则询问）
- [ ] commit 已执行
- [ ] push 已执行（仅当用户明确要求）