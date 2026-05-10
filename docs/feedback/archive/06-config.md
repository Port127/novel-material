# 配置与项目结构

## Skills 外部项目使用

### 问题
skills 配置无法让外部项目使用。

### 解决
- 抽取 skills 到独立配置文件
- 支持外部项目引用 skills 定义

### 相关文件
- `.claude/skills/`

### 归档日期
2026-05-10

---

## 配置文件整合

### 问题
.env 中存放配置项，希望迁移到 config 文件以便追踪变更。

### 解决
- .env 仅存放敏感 key
- 其他配置迁移到 config.yaml
- 配置变更可通过 git 追踪

### 相关文件
- `config/config.yaml`

### 归档日期
2026-05-10

---

## 项目结构整理

### 问题
项目结构凌乱，特别是 scripts 目录，没有项目的样子。

### 解决
- 规划 scripts 目录结构
- 考虑管理、拓展、开发、发布、命名等维度
- 添加 Makefile 统一入口

### 状态
长期优化项

### 归档日期
2026-05-10

---

## 数据库迁移脚本位置

### 问题
数据库迁移写在 schema.sql 中，是否符合业内规范？

### 解决
- 统一到 schema.sql 定义表结构
- 迁移脚本单独管理（如 init 命令）
- 参考 Django/Flask 等框架的迁移实践

### 相关文件
- `data/db/schema.sql`

### 归档日期
2026-05-10

---

## 文档位置调整

### 问题
AGENTS.md、ARCHITECTURE.md 在 docs 目录中，但应起到 harness 指导作用。

### 解决
- 移到项目根目录或 `.claude/` 目录
- 作为 AI 协作指导文档

### 相关文件
- `AGENTS.md`
- `ARCHITECTURE.md`

### 归档日期
2026-05-10

---

## Schemas 目录检查

### 问题
data/schemas 是否仍然合适？需要检查并调整。

### 解决
- 检查 schemas 定义是否符合当前需求
- 更新过时的 schema 定义

### 相关文件
- `data/schemas/*.yaml`

### 归档日期
2026-05-10

---

## 文档与 Skills 更新记录

### 问题
需要更新文档（AGENTS.md、ARCHITECTURE.md、README.md、USER_MANUAL.md）、Makefile 和 skills。

### 解决
- 更新 AGENTS.md：AI 协作指南
- 更新 ARCHITECTURE.md：项目架构文档
- 更新 README.md：使用说明
- 更新 USER_MANUAL.md：用户手册
- 更新 Makefile：常用命令入口
- 更新 skills：LLM 分析技能定义

### 状态
已完成

### 归档日期
2026-05-10

---

## RETRIEVAL_IMPROVEMENT.md 讨论

### 问题
docs 目录有 RETRIEVAL_IMPROVEMENT.md 文件，需要讨论其用途。

### 解决
- 确认该文件为检索优化讨论草稿
- 内容已整合到实际检索实现中
- 文件可归档或删除

### 状态
已确认

### 归档日期
2026-05-10