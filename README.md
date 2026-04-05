# Novel Material

独立的小说素材管理库，为 AI 辅助小说写作系统提供共享素材检索服务。

## 功能

- 素材入库与元数据管理
- 按剧情功能检索（第一幕-诱因、转折点等）
- 按人物原型检索（导师型、反派型等）
- 素材分段切分与索引
- 标签规范化治理

## 与小说项目的关系

本库独立存在，小说项目通过文件路径引用：

```
../novel-material/data/index.yaml
```

## 使用方式

在 Cursor / Claude Code 中打开本目录，使用命令操作。完整命令列表见 [AGENTS.md](AGENTS.md)。

常用命令：
- `/novel-pipeline full [路径]` — 一键完整处理
- `/material-search [关键词]` — 关键词检索
- `/material-search-scene [需求描述]` — 多维标签检索

## 目录说明

| 目录 | 内容 |
|------|------|
| `data/novels/` | 每部小说独立文件夹（原文+大纲+人物+场景+索引） |
| `data/index.yaml` | 素材路由表 |
| `data/tags.yaml` | 标签维度字典（6 层 19 维） |
| `docs/` | 设计文档、schema 模板、计划 |
| `scripts/` | 固化处理脚本 |
| `.claude/skills/` | Agent skill 定义 |