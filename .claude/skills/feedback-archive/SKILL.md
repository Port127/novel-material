---
name: feedback-archive
description: 归档已解决的 feedback 条目。扫描 docs/feedback.md 中带删除线的条目，推断相关 commit 和文件，转换为规范格式后追加到 docs/feedback/archive/，需整体审核确认后执行。仅手动触发。
---

# feedback-archive

归档 docs/feedback.md 中已解决的问题到 docs/feedback/archive/。

**注意：此 skill 仅手动触发，不会自动执行。**

## 前置条件

- docs/feedback.md 存在且包含 `~~删除线~~` 条目
- docs/feedback/archive/ 目录存在

## 执行流程

### 1. 扫描

读取 `docs/feedback.md`，提取所有带 `~~删除线~~` 的条目，保留其所属 section 上下文。

### 2. 分类

根据关键词匹配 archive 文件：

| archive 文件 | 匹配关键词 |
|-------------|-----------|
| 01-progress.md | 进度、进度条、阶段、反馈、展示 |
| 02-logging.md | 日志、打印、输出、时间戳 |
| 03-pipeline.md | pipeline、流水线、流程、continue、入库、阶段 |
| 04-llm.md | LLM、API、模型、向量化、embedding |
| 05-tags.md | 标签、tag |
| 06-config.md | 配置、cli、命令、参数、打包 |
| 07-misc.md | 其他无法分类的 |

无法匹配时创建新文件。新文件编号为 `{现有最大编号+1}`，如现有最大为 07，则新文件为 `08-{主题}.md`；若已有 08，则为 `09-{主题}.md`，以此类推。

### 3. 推断

对每个条目依次执行：

1. **git log 查相关 commit**（最近 30 天）：
   ```bash
   git log --oneline --since="30 days ago" --grep="<关键词>"
   ```
   找到则提取 commit hash 和 message。

2. **git grep 查相关文件**：
   ```bash
   git grep -l "<关键词>" -- "*.py"
   ```
   找到则提取文件路径。

3. **仍未找到**：标记"未定位到相关代码记录"。

### 4. 审核（整体）

汇总展示所有条目预览：

```
共扫描到 X 个已解决条目

--- 条目 1 ---
原始: ~~执行nm pipeline continue时没有日志~~
归档: 02-logging.md
commit: a613140 docs(feedback): 更新反馈文档
文件: src/novel_material/cli/pipeline.py

--- 条目 2 ---
原始: ~~进度条一直卡在2%~~
归档: 01-progress.md
commit: 未定位到相关代码记录
文件: src/novel_material/pipeline/progress.py

--- 条目 3 ---
...

请确认以上归档内容：
- 输入序号可修改单个条目（如输入"1"修改条目1的归档文件或内容）
- 输入"接受"执行全部归档
- 输入"取消"中止
```

用户操作：
- **序号（如 1、2）**：修改指定条目的归档文件或内容
- **接受**：执行全部归档
- **取消**：中止，不执行任何操作

### 5. 执行

审核通过后：

1. 追加到对应 archive 文件，格式：

```markdown
## {问题标题}

### 问题
{原始条目内容，去除删除线}

### 解决
{推断的 commit message 或用户补充内容}

### 相关文件
{推断的文件列表 或 "未定位到相关代码记录"}

### 归档日期
{当前日期}
```

2. 新主题创建新 archive 文件（编号递增）
3. 从 feedback.md 移除已归档条目（含删除线标记的整行）

## 注意事项

- **不去重**：archive 中允许重复内容，重复出现反映问题重要性
- **section 保留**：移除条目后，如 section 变空则保留 section 标题（可能后续添加新条目）
- **编号动态递增**：新 archive 文件编号不固定为 08，根据现有最大编号递增

## 输出示例

```
扫描到 5 个已解决条目
归档完成：
  - 01-progress.md: +2 条
  - 02-logging.md: +1 条
  - 08-ui.md: +2 条（新建）
feedback.md 已清理，移除 5 条
```