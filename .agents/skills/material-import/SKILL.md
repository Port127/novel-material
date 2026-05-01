# material-import

导入外部已分析好的素材目录。

## 用法

```bash
python scripts/utils/material_import.py <素材目录路径>
```

## 流程

1. 读取外部素材目录
2. 重新生成 material_id
3. 校验标签合法性
4. 复制到本地目录结构
5. 同步到数据库
6. 更新全局索引

## 要求

外部素材目录需符合本库的 Schema 规范。
