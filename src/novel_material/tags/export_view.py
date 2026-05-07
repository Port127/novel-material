"""导出标签数据库为 YAML（人读视图）。

注意：此 YAML 文件仅为导出视图，不参与任何代码逻辑。
数据库是唯一数据源。
"""
import os
import yaml
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from novel_material.infra.config import PROJECT_ROOT, DATA_DIR

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """获取数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


def export_tags_view(output_path="data/tags_view.yaml"):
    """导出标签数据库为 YAML 文件供人工查看。

    输出结构:
        dimension:
          domain:
            group:
              - tag1
              - tag2

    示例:
        python export_view.py
        python export_view.py --output custom.yaml
    """
    conn = get_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT dimension, domain, group_name, tag, synonym_of, is_common
            FROM tags ORDER BY dimension, domain, group_name, tag
        """)
        tags = cur.fetchall()

    # 组织成嵌套结构
    result = {}

    for row in tags:
        dim = row["dimension"]
        domain = row["domain"]
        group = row["group_name"] or "未分组"
        tag = row["tag"]

        # 同义词不显示在主列表
        if row["synonym_of"]:
            continue

        if dim not in result:
            result[dim] = {}
        if domain not in result[dim]:
            result[dim][domain] = {}
        if group not in result[dim][domain]:
            result[dim][domain][group] = []

        result[dim][domain][group].append(tag)

    # 同义词映射
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tag, synonym_of FROM tags
            WHERE synonym_of IS NOT NULL ORDER BY synonym_of, tag
        """)
        synonyms = cur.fetchall()

    result["synonym_map"] = {}
    for row in synonyms:
        std = row[1]
        syn = row[0]
        if std not in result["synonym_map"]:
            result["synonym_map"][std] = []
        result["synonym_map"][std].append(syn)

    # 题材领域映射（供参考）
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT genre_primary, domains FROM genre_domain_map ORDER BY genre_primary
        """)
        genre_map = cur.fetchall()

    result["genre_domain_map"] = {}
    for row in genre_map:
        result["genre_domain_map"][row["genre_primary"]] = row["domains"]

    conn.close()

    # 写入 YAML
    output_file = PROJECT_ROOT / output_path
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"已导出到 {output_file}")
    print(f"  标签总数: {len(tags)}")
    print(f"  同义词数: {len(synonyms)}")
    print(f"  题材数: {len(genre_map)}")
    print()
    print("注意: 此 YAML 文件仅为导出视图，不参与任何代码逻辑。")
    print("数据库是唯一数据源。")


if __name__ == "__main__":
    import sys
    output = "data/tags_view.yaml"
    if len(sys.argv) >= 3 and sys.argv[1] == "--output":
        output = sys.argv[2]

    export_tags_view(output)