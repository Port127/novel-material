---
name: material-import
description: 导入外部已分析好的素材（按本库 schema 格式），注册到素材库
when_to_use: 用户有一个按本库 schema 组织好的文件夹，想直接注册进来而不重跑 pipeline
argument-hint: "[文件夹路径] [--name 书名] [--author 作者]"
arguments: folder_path, name, author
---

# 任务

将外部已分析好的素材文件夹导入素材库。文件必须遵循本库的 schema 格式。

**与 `material-add` 的区别**：`material-add` 只入库原文（status=raw），后续需要跑 pipeline 分析。`material-import` 接收已完成分析的文件，直接注册到可检索状态。

## 输入参数

- `$0` (folder_path): 包含已分析素材的文件夹路径
- `--name`: 书名（可选，如不提供则从文件中提取）
- `--author`: 作者（可选，如不提供则从文件中提取）

## 预期文件夹结构

导入文件夹应包含以下文件（均可选，至少提供一个分析产出物）：

```
imported_folder/
├── source.txt              # 原文（可选）
├── outline/                # 大纲文件夹（新格式）或 outline.yaml（旧格式）
│   ├── _index.yaml
│   ├── structure.yaml
│   └── ...
├── worldbuilding/          # 世界观文件夹（新格式）或 worldbuilding.yaml（旧格式）
│   ├── _index.yaml
│   └── ...
├── characters/             # 人物文件夹（新格式）或 characters.yaml（旧格式）
│   ├── _index.yaml
│   ├── relations.yaml
│   └── profiles/*.yaml
├── tags.yaml               # 小说级标签
├── events/                 # 事件文件夹
│   ├── ch0001_s01.yaml
│   ├── ch0001_s02.yaml
│   └── ...
├── events_index.yaml       # 倒排索引（可选，可重建）
├── events_manifest.yaml    # 事件清单（可选，可重建）
├── stats.yaml              # 统计数据（可选）
├── stats.md                # 可视化报告（可选）
└── stats.html              # 交互报告（可选）
```

**兼容性说明**：导入时支持两种格式：
- 新格式（文件夹结构）：outline/、worldbuilding/、characters/ 文件夹
- 旧格式（单文件）：outline.yaml、worldbuilding.yaml、characters.yaml

导入后会统一转换为新的文件夹结构。

如果文件夹中有 `meta.yaml`，读取其中的 `name` 和 `author`，但 `material_id` 一律重新生成。

## 执行步骤

### 1. 扫描文件夹

列出文件夹内所有文件，分类统计：

```yaml
scan_result:
  source: true/false
  outline: true/false
  worldbuilding: true/false
  characters: true/false
  tags: true/false
  events_count: N          # events/ 下 ev*.yaml 文件数
  events_index: true/false
  events_manifest: true/false
  stats: true/false
  stats_md: true/false
  stats_html: true/false
  unknown_files: [...]     # 不认识的文件，列出供用户确认
```

如果没有任何分析产出物（全是 false），报错退出。

### 2. 提取元信息

按优先级获取书名和作者：

1. 命令行 `--name` / `--author` 参数
2. 文件夹中 `meta.yaml` 的 `name` / `author` 字段
3. `outline/_index.yaml` 或 `outline.yaml` 中的 `title` / `author` 字段
4. 文件夹名称推断

如果最终无法确定，询问用户。

### 3. 校验文件格式

对每个存在的文件执行校验：

| 文件 | 校验内容 |
|------|---------|
| outline/_index.yaml 或 outline.yaml | YAML 可解析 + 结构字段存在 |
| worldbuilding/_index.yaml 或 worldbuilding.yaml | YAML 可解析 |
| characters/_index.yaml 或 characters.yaml | YAML 可解析 + `roster` 字段存在 |
| tags.yaml | YAML 可解析 + 标签值在 `data/tags.yaml` 字典中 |
| events/*.yaml | YAML 可解析 + 必填字段（id, chapter, title, summary, event_type）+ 标签值合法 |

**标签合法性检查**：扫描所有文件中的标签值，与 `data/tags.yaml` 对比。

- 合法值 → 通过
- 不合法值 → 收集到列表，在预览中展示，询问用户：
  - 自动忽略非法值
  - 用 `/tag-add` 新增到字典
  - 终止导入

校验失败的文件不会阻止导入，但在预览中标记为 `⚠️`，导入后 status 不会高于其对应阶段。

### 4. 推断 status

根据通过校验的文件推断素材状态：

| 条件 | status |
|------|--------|
| 有 events/ 且通过校验 + 有索引 + 有 refine 痕迹 | `refined` |
| 有 events/ 且通过校验 + 有索引 | `complete` |
| 有 events/ 且通过校验 | `complete`（后续自动建索引） |
| 有 tags.yaml | `tagged` |
| 有 outline/ 或 outline.yaml | `outlined` |
| 仅有 source.txt | `raw` |

### 5. 预览

```
📋 素材导入预览

来源：{folder_path}
书名：{name}
作者：{author}

检测到的文件：
  ✅ source.txt          (原文)
  ✅ outline/ 或 outline.yaml (大纲)
  ✅ worldbuilding/ 或 worldbuilding.yaml (世界观)
  ✅ characters/ 或 characters.yaml (人物体系)
  ✅ tags.yaml           (小说级标签)
  ✅ events/             ({N} 个事件文件)
  ❌ events_index.yaml   (缺失，将自动构建)
  ❌ events_manifest.yaml(缺失，将自动构建)

{如有标签问题}
  ⚠️ 标签合法性：
    - event_type 中 "群殴" 不在字典中
    - emotion 中 "窒息感" 不在字典中
    选择：(1) 自动新增到字典 (2) 忽略非法值 (3) 终止

推断状态：{status}

将执行：
  1. 生成 material_id
  2. 复制文件到 data/novels/{id}/
  3. 写入 meta.yaml + 更新 index.yaml
  {如有 events} 4. 运行 build-index 构建索引

确认导入？(yes/no)
```

### 6. 去重检查

读取 `data/index.yaml`，检查书名是否与已有素材相似。如果疑似重复，提醒用户确认。

### 7. 执行导入

用户确认后：

1. **生成 material_id**：`nm_novel_{YYYYMMDD}_{random4}`
2. **创建文件夹**：`data/novels/{material_id}/`
3. **复制文件**：将所有通过校验的文件复制到目标文件夹
4. **写入 meta.yaml**：

```yaml
material_id: {id}
type: novel
name: "{name}"
author: {author}
source: source.txt      # 如有
added: {today}
status: {inferred_status}
imported: true
import_source: {original_folder_path}
pipeline:
  mode: import
  stages_completed: [{根据有哪些文件推断}]
  formatted: {true if source.txt exists}
```

5. **更新 index.yaml**
6. **自动构建索引**（如有 events 但缺 index/manifest）：
   - 读取并执行 `build-index/SKILL.md`
   - 或直接运行 `python scripts/core/build_event_index.py {material_id}` + `python scripts/core/build_db.py --material {material_id}`

### 8. 输出报告

```
✅ 素材导入完成

📚 ID：{material_id}
📄 名称：{name}
📁 文件夹：data/novels/{material_id}/
📋 状态：{status}

导入文件：
  - outline/ 或 outline.yaml ✅
  - worldbuilding/ 或 worldbuilding.yaml ✅
  - characters/ 或 characters.yaml ✅
  - tags.yaml           ✅
  - events/ ({N}个)     ✅
  - events_index.yaml   ✅ (自动构建)
  - events_manifest.yaml ✅ (自动构建)

{如果 status 不是 refined}
后续操作：
  /pipeline-events {id}     # 补充事件拆分（如部分缺失）
  /pipeline-finalize {id}   # 精调+统计报告
```

## 硬约束

- MUST 重新生成 material_id，不复用外部 meta.yaml 的 ID
- MUST 校验所有 YAML 文件可解析
- MUST 检查标签值合法性，不合法值需用户决定处理方式
- MUST 在预览中展示所有检测结果，等待用户确认
- MUST 导入后如有 events 缺索引，自动构建
- NEVER 直接移动源文件夹（复制，不删除原始）
- NEVER 跳过去重检查

## References

- [material-add/SKILL.md](../material-add/SKILL.md)
- [build-index/SKILL.md](../build-index/SKILL.md)
- [docs/schemas/](../../../docs/schemas/)
- [AGENTS.md](../../../AGENTS.md)
