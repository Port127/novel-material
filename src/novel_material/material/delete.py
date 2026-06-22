"""删除素材及其所有关联资源。"""
import os
import sys
import shutil
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from novel_material.infra.config import NOVELS_DIR, INDEX_FILE
from novel_material.infra.yaml_io import load_yaml, save_yaml
from novel_material.material.audit import emit_material_audit
from novel_material.runtime.contracts import RunStatus
from novel_material.runtime.dispatcher import NullDispatcher, RuntimeDispatcher

DATABASE_URL = os.getenv("DATABASE_URL")


def delete_material(
    material_id,
    confirm=True,
    *,
    novels_dir=NOVELS_DIR,
    dispatcher: RuntimeDispatcher | None = None,
):
    """删除指定素材。"""
    event_dispatcher = dispatcher or NullDispatcher()
    emit_material_audit(
        event_dispatcher,
        operation="material.delete",
        object_id=material_id,
        phase="started",
    )
    novel_dir = novels_dir / material_id

    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        emit_material_audit(
            event_dispatcher,
            operation="material.delete",
            object_id=material_id,
            phase="failed",
            status=RunStatus.FAILED,
        )
        return False

    meta_file = novel_dir / "meta.yaml"
    meta = load_yaml(meta_file)

    novel_name = meta.get("name", material_id)

    if confirm:
        print(f"警告: 即将删除以下素材:")
        print(f"  material_id: {material_id}")
        print(f"  名称: {novel_name}")
        print(f"  路径: {novel_dir}")
        print(f"\n这将删除:")
        print(f"  1. 目录: {novel_dir}")
        print(f"  2. 数据库记录 (novels/chapters/characters/worldbuilding/outline)")
        print(f"  3. 全局索引中的记录")
        print(f"\n此操作不可逆!")

        response = input("\n确认删除? (输入 YES 认): ")
        if response != "YES":
            print("操作已取消")
            emit_material_audit(
                event_dispatcher,
                operation="material.delete",
                object_id=material_id,
                phase="failed",
                status=RunStatus.FAILED,
            )
            return False

    # 1. 删除目录
    print(f"\n正在删除目录: {novel_dir}")
    shutil.rmtree(novel_dir)
    print("目录已删除")

    # 2. 删除数据库记录
    if DATABASE_URL:
        print("\n正在删除数据库记录...")
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = False

            with conn.cursor() as cur:
                cur.execute("DELETE FROM novels WHERE material_id = %s", (material_id,))
                deleted_rows = cur.rowcount
                print(f"已删除 novels 表记录: {deleted_rows}")

            conn.commit()
            print("数据库记录已删除")
            conn.close()

        except Exception as e:
            print(f"数据库删除失败: {e}")
            print("请手动清理数据库")

    # 3. 更新全局索引
    index_file = INDEX_FILE
    if index_file.exists():
        index = load_yaml(index_file)

        if material_id in index:
            del index[material_id]
            save_yaml(index_file, index)
            print("全局索引已更新")

    print(f"\n删除完成: {material_id}")
    emit_material_audit(
        event_dispatcher,
        operation="material.delete",
        object_id=material_id,
        phase="completed",
        status=RunStatus.SUCCESS,
    )
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="删除素材及所有关联资源")
    parser.add_argument("--id", dest="material_id", required=True, help="素材 ID")
    args = parser.parse_args()
    delete_material(args.material_id)
