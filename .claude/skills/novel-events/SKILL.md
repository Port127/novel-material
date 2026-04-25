---
name: novel-events
description: 将小说按事件单元拆分并打多维标签；支持 scan、范围处理和 all 模式的自动分批执行
---

# 任务

把原文拆成**事件单元**，为每个事件生成结构化 YAML 和多维标签。

默认目标：

1. 事件边界可信
2. 标签来自真实阅读理解，不是关键词糊弄
3. 每批写入后立即校验和审计
4. `all` 模式自动循环，不逐批询问

## 输入模式

| 调用方式 | 行为 |
|----------|------|
| `/novel-events {id} scan` | 只扫描线索与边界，不写事件文件 |
| `/novel-events {id}` | 默认处理前 30 章 |
| `/novel-events {id} 31-60` | 处理指定章节范围 |
| `/novel-events {id} all` | 全书自动分批：扫描 → 边界草案 → 批量产出 → 覆盖修补 → 交汇检测 |

## 适用边界

用于：
- 为 `pipeline-events` 产出事件 YAML
- 局部重做某个章节范围
- 先扫描全书线索，再进入正式拆分

不用于：
- build-index
- refine
- 用脚本批量模板化生成事件

## 默认执行路径

### 1. 前置检查

开始前必须确认：

- `meta.yaml`、`source.txt`、`chapter_index.yaml` 存在
- 标签字典来自 `data/tags.yaml`
- 事件 schema 以 `docs/schemas/event-unit.schema.yaml` 为准

### 2. `scan` 模式

只做两件事：

1. 识别叙事线索，生成或更新 `threads_manifest.yaml`
2. 粗扫事件边界，生成 `events_manifest_draft.yaml`

**scan 不写正式事件 YAML。**

### 3. 范围模式

对指定章节范围执行：

1. 读本批原文
2. 识别事件边界
3. 为每个事件写 YAML
4. 运行 schema 校验与批次审计

### 4. `all` 模式

按以下顺序自动执行：

1. 全书线索扫描
2. 全书边界草案
3. 分批读取原文并生成事件
4. 每批写完立即运行：

```bash
python scripts/core/quality_audit.py {material_id} --batch {本批范围}
```

5. 全书写完后检查主线覆盖缺口，必要时自动补切
6. 扫描跨线索交汇，写入 `events/cross_thread_events.yaml`

`all` 模式下**无需逐批确认**。只要本轮还能继续，就继续执行。

## 每批最低要求

每批都必须完成以下动作，缺一不可：

1. 只读取本批相关章节
2. 写入本批事件 YAML
3. 运行 YAML 校验
4. 运行 `quality_audit.py --batch {本批范围}`
5. 更新 `meta.yaml` 中的事件进度

## 核心硬约束

- 标签必须从 `data/tags.yaml` 选取
- `chapter` 字段必须从 `chapter_index.yaml` 逐字拷贝
- 含引号的字符串值使用单引号包裹
- `lines` 优先精确定位；做不到时必须写 `lines_approximate: true`
- 主线连续未覆盖章节不得超过 3
- 同章内两个独立戏剧动作必须拆分
- 回忆 / 闪回不能替代对正文主线覆盖
- 事件标签必须由阅读理解生成，禁止脚本批量生成模板事件

## 钩子处理边界

本阶段只负责：

- 章末悬念
- 道具钩子
- 显性的跨事件铆合点

隐性的：

- 人物钩子
- 信息钩子
- 情感钩子

留给 `refine` 做全局验证。

## 输出

至少可能产出：

- `events/*.yaml`
- `events/threads_manifest.yaml`
- `events/events_manifest_draft.yaml`
- `events/cross_thread_events.yaml`

## 失败时必须报告

- 停在哪一批 / 哪个范围
- 校验失败还是审计失败
- 哪些章节仍未覆盖
- 是否需要重新 scan 或补切

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/segmentation-rules.md`
- `references/hook-rules.md`
- `references/output-examples.md`
- `../../../docs/schemas/event-unit.schema.yaml`
- `../../../AGENTS.md`
