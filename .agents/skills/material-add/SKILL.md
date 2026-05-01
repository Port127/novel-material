# material-add

将新小说添加到共享素材库。

## 用法

```bash
python scripts/pipeline.py full <小说文件路径>
```

## 流程

1. 生成唯一 material_id (`nm_novel_YYYYMMDD_xxxx`)
2. 创建目录结构 (`data/novels/{material_id}/`)
3. 格式清洗 + 章节切分
4. 生成 meta.yaml
5. 运行章级分析（LLM）
6. 同步到 PostgreSQL

## 产物

```
data/novels/{material_id}/
├── meta.yaml
├── source.txt              # 清洗后原文
├── chapter_index.yaml      # 章节索引
├── chapters.yaml           # 章级分析
├── outline/
├── characters/
└── worldbuilding/
```

## 校验

运行后检查：
- chapter_index.yaml 是否生成
- chapters.yaml 是否有数据
- 数据库中是否有记录
