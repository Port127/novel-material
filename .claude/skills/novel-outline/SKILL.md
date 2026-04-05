---
name: novel-outline
description: 读取小说原文，生成故事大纲（结构、节奏、伏笔）
when_to_use: 用户想要为入库小说生成大纲骨架
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

读取小说原文，生成结构化故事大纲。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/novels/{material_id}/meta.yaml`
3. 读取 `data/novels/{material_id}/source.txt`

## Schema

输出遵循 `docs/schemas/outline.schema.yaml`。

## 执行步骤

### 1. 通读全文

理解全书叙事结构、主要情节线、转折点。

### 2. 提取结构骨架

按幕/卷划分，标注：
- 每幕覆盖的章节范围
- 主要叙事弧线
- 核心事件
- 转折点
- 节奏特征

### 3. 识别时间线

如果存在多线叙事、双时间线，分别标注各线覆盖的章节。

### 4. 追踪伏笔

找出主要伏笔的埋设点和回收点，记录章节号和描述。

### 5. 标注节奏曲线

选取关键章节（开篇、中点、高潮等），标注 tension 值（1-5）和简要说明。

### 6. 写入 outline.yaml

写入 `data/novels/{material_id}/outline.yaml`。

### 7. 更新状态

将 `meta.yaml` 中 `status` 更新为 `outlined`（如果当前是 `raw`）。

## 输出格式

```
✅ 大纲已生成

📚 素材：{name}
🏗️ 结构：{N}幕
📈 伏笔：{M}条
📁 文件：data/novels/{id}/outline.yaml

后续步骤：
  /novel-characters {id}    # 生成人物体系
```

## 注意事项

- 大纲是全书骨架，不需要场景级细节
- premise 用一句话概括核心前提
- 伏笔只记录主要的，不需要穷举
- 长篇小说可能需要分卷阅读
