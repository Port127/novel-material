#!/usr/bin/env python
"""删除素材及其所有关联资源（目录 + 数据库记录 + 全局索引）。"""
import os
import sys
import yaml
import shutil
import psycopg2
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def delete_material(material_id, confirm=True):
    """删除指定素材。"""
    novel_dir = Path("data/novels") / material_id

    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return False

    # 读取 meta 确认
    meta_file = novel_dir / "meta.yaml"
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

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

        response = input("\n确认删除? (输入 YES 确认): ")
        if response != "YES":
            print("操作已取消")
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
                # 删除所有关联表（使用 CASCADE 自动删除）
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
    index_file = Path("data/index.yaml")
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f) or {}

        if material_id in index:
            del index[material_id]
            with open(index_file, "w", encoding="utf-8") as f:
                yaml.dump(index, f, allow_unicode=True, default_flow_style=False)
            print("全局索引已更新")

    print(f"\n删除完成: {material_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python material_delete.py <material_id>")
        sys.exit(1)

    delete_material(sys.argv[1])
