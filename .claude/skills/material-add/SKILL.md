---
name: material-add
description: 添加素材到共享素材库
when_to_use: 用户想要添加参考素材
argument-hint: "[路径] [--type novel|image|reference]"
arguments: path
---

# 任务

添加素材到共享素材库，创建独立文件夹。

## 输入参数

- `$0` (path): 素材文件路径
- `--type`: 类型（novel/image/reference），默认 novel

## 执行步骤

### 1. 检查素材

- 确认文件存在
- 确认类型

### 2. 生成素材 ID

格式：`nm_{type}_{YYYYMMDD}_{random4}`

### 3. 创建文件夹结构

```bash
data/novels/{material_id}/
├── meta.yaml
├── source.txt     # 复制原文
└── scenes/        # 空目录
```

### 4. 写入 meta.yaml

参照 `docs/schemas/meta.schema.yaml`：

```yaml
material_id: {id}
type: novel
name: "《书名》"
author: 作者名
source: source.txt
added: {today}
status: raw
```

### 5. 更新 index.yaml

在 `data/index.yaml` 的 `materials` 列表追加：

```yaml
- id: {id}
  type: novel
  name: "《书名》"
  author: 作者名
  folder: data/novels/{id}
  status: raw
  added: {today}
```

## 输出格式

```
✅ 素材已入库

📚 ID：{id}
📄 名称：{name}
📁 文件夹：data/novels/{id}/
📋 状态：raw

后续步骤：
  /novel-outline {id}       # 生成大纲
  /novel-characters {id}    # 生成人物体系
  /novel-tags {id}          # 生成小说级标签
  /novel-scenes {id} 1-5    # 拆分场景（按章节范围）
```

## 注意事项

- 大文件直接存入 source.txt，不做切分
- ID 跨项目唯一
- 入库后 status=raw，等待后续 skill 处理
