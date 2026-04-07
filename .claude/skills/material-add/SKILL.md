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

### 2. 去重检查

读取 `data/index.yaml`，对现有 materials 逐条检查：

- **书名匹配**：新素材的书名（从文件名提取）与已有 `name` 字段相似
- **文件名匹配**：新素材文件路径与已入库的任何文件路径相同

如果发现疑似重复：

```
⚠️ 疑似重复素材

已有记录：
  ID：nm_novel_20260405_k8m2
  名称：《三体1》地球往事（实体版拆分）
  状态：raw

当前素材：
  文件：/path/to/三体1.txt

是否仍要入库？(yes/no)
```

用户确认后才继续。如果确认入库，说明是同书不同版本，正常创建新 ID。

### 3. 生成素材 ID

格式：`nm_{type}_{YYYYMMDD}_{random4}`

生成后检查 `data/index.yaml` 确认 ID 不冲突（极小概率的 random4 碰撞）。

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
- ID 跨项目唯一，生成后需验证不冲突
- 入库后 status=raw，等待后续 skill 处理
- 同一部小说的不同版本（如实体版/网络版）可以各自入库，去重检查只做提醒不做阻断

## References

- [meta.schema.yaml](../../../docs/schemas/meta.schema.yaml)
- [AGENTS.md](../../AGENTS.md)
