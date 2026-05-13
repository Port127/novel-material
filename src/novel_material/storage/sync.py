"""数据库同步：把本地 YAML 文件同步到 PostgreSQL。

自动修复：
- 检测到 summary 长度不足、章节缺失或 schema 错误时会自动调用修复接口重试
- 修复成功后继续同步，失败则返回 False

模块拆分：
- sync_utils.py：公共函数和异常类
- sync_meta.py：同步 meta.yaml
- sync_chapters.py：同步章节数据和人物出场
- sync_outline.py：同步大纲结构
- sync_characters.py：同步人物档案
- sync_worldbuilding.py：同步世界观元素
- sync_core.py：入口函数（sync_novel, sync_all）
- sync.py：统一入口（向后兼容）
"""
import sys

# 从子模块导入所有函数，向后兼容
from novel_material.storage.sync_utils import (
    _load_embeddings_npz,
    DatabaseConfigError,
    QualityCheckError,
    SchemaValidationError,
    get_db_connection,
)
from novel_material.storage.sync_core import (
    sync_novel,
    sync_all,
)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python sync.py <material_id> 或 python sync.py all")
        sys.exit(1)

    if sys.argv[1] == "all":
        count = sync_all()
        print(f"已同步 {count} 个素材")
    else:
        success = sync_novel(sys.argv[1])
        if success:
            print(f"同步完成: {sys.argv[1]}")
        else:
            print(f"同步失败: {sys.argv[1]}")
            sys.exit(1)