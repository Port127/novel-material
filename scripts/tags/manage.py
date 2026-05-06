#!/usr/bin/env python
"""标签管理 CLI 工具。

提供添加、删除、移动、导出、统计等功能。
"""
import os
import sys
import click
import psycopg2
import psycopg2.extras
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("错误: 请设置 DATABASE_URL 环境变量")
    sys.exit(1)


def get_connection():
    """获取数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


@click.group()
def cli():
    """标签管理工具"""
    pass


@cli.command()
@click.argument("dimension")
@click.argument("tag")
@click.argument("domain")
@click.option("--group", default=None, help="分组名")
@click.option("--synonym-of", default=None, help="同义词指向的标准标签")
@click.option("--description", default=None, help="标签说明")
def add(dimension, tag, domain, group, synonym_of, description):
    """添加标签到数据库。

    示例:
        python manage.py add element 血脉 xuanhuan --group 设定元素
        python manage.py add element 血脉觉醒 xuanhuan --synonym-of 血脉
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO tags (dimension, tag, domain, group_name, is_common, synonym_of, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (dimension, tag) DO UPDATE SET
                domain = EXCLUDED.domain,
                group_name = EXCLUDED.group_name,
                is_common = EXCLUDED.is_common,
                synonym_of = EXCLUDED.synonym_of,
                description = EXCLUDED.description
        """, [dimension, tag, domain, group, domain == "common", synonym_of, description])

    conn.close()
    click.echo(f"已添加: {dimension}/{domain}/{tag}")


@cli.command()
@click.argument("dimension")
@click.argument("tag")
def remove(dimension, tag):
    """删除标签。

    示例:
        python manage.py remove element 血脉
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("DELETE FROM tags WHERE dimension = %s AND tag = %s", [dimension, tag])
        affected = cur.rowcount

    conn.close()
    click.echo(f"已删除: {dimension}/{tag} (影响 {affected} 行)")


@cli.command()
@click.argument("dimension")
@click.argument("tag")
@click.argument("new_domain")
def move(dimension, tag, new_domain):
    """移动标签到其他领域。

    示例:
        python manage.py move element 血脉 xianxia
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE tags SET domain = %s, is_common = %s
            WHERE dimension = %s AND tag = %s
        """, [new_domain, new_domain == "common", dimension, tag])
        affected = cur.rowcount

    conn.close()
    click.echo(f"已移动: {dimension}/{tag} → {new_domain} (影响 {affected} 行)")


@cli.command()
@click.argument("dimension")
@click.argument("tag")
@click.argument("standard_tag")
def set_synonym(dimension, tag, standard_tag):
    """设置同义词关系。

    示例:
        python manage.py set-synonym element 血脉觉醒 血脉
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE tags SET synonym_of = %s
            WHERE dimension = %s AND tag = %s
        """, [standard_tag, dimension, tag])
        affected = cur.rowcount

    conn.close()
    click.echo(f"已设置: {tag} → {standard_tag} (影响 {affected} 行)")


@cli.command()
def export():
    """导出 YAML 视图供人阅读。

    示例:
        python manage.py export
    """
    from scripts.tags.export_view import export_tags_view
    export_tags_view()
    click.echo("已导出到 data/tags_view.yaml")


@cli.command()
def stats():
    """统计各维度标签数量。

    示例:
        python manage.py stats
    """
    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT dimension, domain, COUNT(*) as count
            FROM tags GROUP BY dimension, domain ORDER BY dimension, domain
        """)

        current_dim = None
        for row in cur.fetchall():
            dim, dom, count = row
            if dim != current_dim:
                click.echo(f"\n{dim}:")
                current_dim = dim
            click.echo(f"  {dom}: {count} 个")

    # 同义词统计
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tags WHERE synonym_of IS NOT NULL")
        syn_count = cur.fetchone()[0]
        click.echo(f"\n同义词: {syn_count} 个")

    conn.close()


@cli.command()
@click.option("--dimension", default=None, help="筛选维度")
@click.option("--domain", default=None, help="筛选领域")
@click.option("--limit", default=50, help="显示数量")
def list_tags(dimension, domain, limit):
    """列出标签。

    示例:
        python manage.py list-tags
        python manage.py list-tags --dimension element
        python manage.py list-tags --dimension element --domain xuanhuan
    """
    conn = get_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        sql = "SELECT dimension, tag, domain, group_name, synonym_of FROM tags WHERE synonym_of IS NULL"
        params = []

        if dimension:
            sql += " AND dimension = %s"
            params.append(dimension)

        if domain:
            sql += " AND domain = %s"
            params.append(domain)

        sql += " ORDER BY dimension, domain, group_name, tag LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)

        for row in cur.fetchall():
            group = row["group_name"] or "未分组"
            click.echo(f"{row['dimension']}/{row['domain']}/{group}: {row['tag']}")

    conn.close()


@cli.command()
@click.argument("dimension")
@click.argument("tag")
def info(dimension, tag):
    """查看标签详细信息。

    示例:
        python manage.py info element 血脉
    """
    conn = get_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM tags WHERE dimension = %s AND tag = %s
        """, [dimension, tag])
        result = cur.fetchone()

    if not result:
        click.echo(f"标签不存在: {dimension}/{tag}")
        conn.close()
        return

    click.echo(f"\n标签: {result['tag']}")
    click.echo(f"维度: {result['dimension']}")
    click.echo(f"领域: {result['domain']}")
    click.echo(f"分组: {result['group_name'] or '未分组'}")
    click.echo(f"通用: {result['is_common']}")
    click.echo(f"同义词指向: {result['synonym_of'] or '无'}")
    click.echo(f"说明: {result['description'] or '无'}")
    click.echo(f"创建时间: {result['created_at']}")

    # 查看同义词
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tag FROM tags WHERE synonym_of = %s AND dimension = %s
        """, [tag, dimension])
        synonyms = [row[0] for row in cur.fetchall()]

    if synonyms:
        click.echo(f"\n同义词: {', '.join(synonyms)}")

    conn.close()


if __name__ == "__main__":
    cli()