# pipeline-ingest

入库 + 格式清洗流水线。

## 用法

```bash
python scripts/core/ingest.py <小说文件路径>
```

## 流程

1. 读取原文文件
2. 检测章节名模式
3. 章节切分
4. 保存 source.txt（清洗后原文）
5. 生成 chapter_index.yaml
6. 生成 meta.yaml
7. 创建空目录结构（outline/characters/worldbuilding）
8. 更新全局索引

## 输出状态

- meta.yaml 中 `status: clean`
