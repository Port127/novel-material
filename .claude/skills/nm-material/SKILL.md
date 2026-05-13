---
name: nm-material
description: >-
  小说素材流水线管理：ingest、analyze、sync、delete。仅当用户明确说出"使用 nm-material"或"启动 nm-material"时触发。不适用于任何隐式场景。
---

# nm-material

小说素材管理中枢，覆盖导入、LLM 分析、数据库同步、删除。

## 触发约束

此 skill **仅通过显式调用触发**。

### ⛔ 不触发的场景
- 用户提到处理 txt 文件、运行流水线但未提及 nm-material
- 日常文件操作或数据库查询
- 用户未显式引用 @nm-material

### ✅ 触发条件
必须同时满足：
1. 用户明确说出"使用 nm-material"或"启动 nm-material"，或显式引用 @nm-material
2. 用户提供了明确的素材处理需求

## Quick Start

| Goal | Command | Notes |
|------|---------|-------|
| Full pipeline | `nm pipeline full <file.txt>` | One-shot: ingest → analyze → sync |
| Resume pipeline | `nm pipeline continue <material_id>` | Resume from breakpoint |
| Import analyzed | `nm material import <dir>` | Skip LLM, direct import |
| Delete material | `nm material delete --id <id> --force` | Destructive, irreversible |

## Pipeline Stages

Stage order: **ingest → analyze → outline → worldbuilding → characters → tags → refine → sync**

### Stage Commands

| Stage | Command | Input | Output |
|-------|---------|-------|--------|
| Ingest | `nm pipeline ingest <file.txt>` | Raw .txt | source.txt, chapter_index.yaml |
| Analyze | `nm pipeline analyze <material_id>` | chapter_index.yaml | chapters.yaml, embeddings |
| Outline | `nm pipeline outline <material_id>` | chapters.yaml | outline/structure.yaml |
| Worldbuilding | `nm pipeline worldbuilding <material_id>` | chapters.yaml | worldbuilding/*.yaml |
| Characters | `nm pipeline characters <material_id>` | chapters.yaml | characters/profiles/*.yaml |
| Tags | `nm pipeline tags <material_id>` | source.txt | tags.yaml |
| Refine | `nm pipeline refine <material_id>` | all YAML | Updated statistics |
| Sync | `nm storage sync <material_id>` | All YAML + vectors | PostgreSQL |

### Stage Status

```bash
nm pipeline status <material_id>
```

Shows completed/pending stages and suggests next command.

## Material Operations

### Import (Skip LLM)

Use for migrating from other instances, importing annotated materials, or restoring backups.

```bash
nm material import <directory>
```

Requirements:
- Directory must match schema in `data/schemas/`
- Must contain `meta.yaml` and `chapter_index.yaml`
- Tags must exist in PostgreSQL `tags` table

### Delete (Destructive)

```bash
nm material delete --id <material_id> --force
```

Deletes:
- Local: `data/novels/{material_id}/` entire directory
- Database: All rows linked to this material_id
- Index: Entry in `data/index.yaml`

**Safety rules:**
- MUST confirm with user before execution
- NEVER batch delete multiple materials

## Prerequisites

- `.env` configured with `LLM_API_KEY` (for analyze stages)
- `.env` configured with `DATABASE_URL` (for sync stage)
- PostgreSQL initialized (`nm storage init-db`)

## Success Verification

After `nm pipeline full`:
1. `data/novels/{material_id}/chapter_index.yaml` exists with chapters > 0
2. `data/novels/{material_id}/chapters.yaml` exists as non-empty list
3. `data/novels/{material_id}/meta.yaml` shows `status: indexed`
4. Terminal shows "流水线完成"

## Failure Handling

| Symptom | Cause | Action |
|---------|-------|--------|
| "未检测到章节名" | Non-standard chapter format | Check file for unusual chapter titles |
| API connection error | Network issue | Auto-retry, no manual intervention needed |
| Mid-crash | Rate limiting etc. | Run `nm pipeline continue` - resumes from breakpoint |