#!/usr/bin/env python
"""新标签审核 CLI 工具。

管理新标签候选和新题材候选的审核流程。
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


def get_connection():
    """获取数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


@click.group()
def cli():
    """新标签审核工具"""
    pass


@cli.command("list")
@click.option("--status", default="pending", help="筛选状态")
@click.option("--dimension", default=None, help="筛选维度")
@click.option("--limit", default=20, help="显示数量")
def list_candidates(status, dimension, limit):
    """列出待审核新标签。

    示例:
        python review.py list
        python review.py list --status auto_approved
        python review.py list --dimension element --limit 50
    """
    conn = get_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        sql = """
            SELECT id, dimension, tag, suggested_domain, context_genre,
                   occurrence_count, status, source_material
            FROM new_tag_candidates
            WHERE status = %s
        """
        params = [status]

        if dimension:
            sql += " AND dimension = %s"
            params.append(dimension)

        sql += " ORDER BY occurrence_count DESC LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)

        for row in cur.fetchall():
            click.echo(f"[{row['id']}] {row['dimension']}/{row['tag']} ({row['occurrence_count']}次)")
            click.echo(f"    来源: {row['source_material']} ({row['context_genre']})")
            click.echo(f"    建议: {row['suggested_domain'] or '未指定'} | 状态: {row['status']}")
            click.echo()

    conn.close()


@cli.command("approve")
@click.argument("candidate_id")
@click.option("--domain", default=None, help="指定领域")
@click.option("--group", default=None, help="指定分组")
def approve(candidate_id, domain, group):
    """批准新标签。

    示例:
        python review.py approve 1 --domain xuanhuan --group 设定元素
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        # 获取候选信息
        cur.execute("SELECT * FROM new_tag_candidates WHERE id = %s", [candidate_id])
        candidate = cur.fetchone()

        if not candidate:
            click.echo(f"候选 ID {candidate_id} 不存在")
            conn.close()
            return

        dimension = candidate[1]
        tag = candidate[2]
        suggested_domain = candidate[3] or domain or "common"

        # 添加到正式标签表
        cur.execute("""
            INSERT INTO tags (dimension, tag, domain, group_name, is_common)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (dimension, tag) DO NOTHING
        """, [dimension, tag, suggested_domain, group, suggested_domain == "common"])

        # 更新候选状态
        cur.execute("""
            UPDATE new_tag_candidates
            SET status = 'approved', reviewed_at = NOW(), reviewed_by = 'manual'
            WHERE id = %s
        """, [candidate_id])

    conn.close()
    click.echo(f"已批准: {dimension}/{suggested_domain}/{tag}")


@cli.command("reject")
@click.argument("candidate_id")
@click.option("--reason", default=None, help="拒绝原因")
def reject(candidate_id, reason):
    """拒绝新标签。

    示例:
        python review.py reject 1 --reason "语义不明确"
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE new_tag_candidates
            SET status = 'rejected', reviewed_at = NOW(), reviewed_by = 'manual'
            WHERE id = %s
        """, [candidate_id])
        affected = cur.rowcount

    conn.close()
    click.echo(f"已拒绝候选 {candidate_id} (影响 {affected} 行)")


@cli.command("list-genres")
@click.option("--status", default="pending")
def list_genre_candidates(status):
    """列出待审核新题材。

    示例:
        python review.py list-genres
    """
    conn = get_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT id, genre, description, occurrence_count, source_material
            FROM new_genre_candidates
            WHERE status = %s
            ORDER BY occurrence_count DESC
        """, [status])

        for row in cur.fetchall():
            click.echo(f"[{row['id']}] {row['genre']} ({row['occurrence_count']}次)")
            click.echo(f"    来源: {row['source_material']}")
            click.echo(f"    描述: {row['description']}")
            click.echo()

    conn.close()


@cli.command("approve-genre")
@click.argument("candidate_id")
@click.option("--domains", default=None, help="领域配置 JSON")
def approve_genre(candidate_id, domains):
    """批准新题材。

    示例:
        python review.py approve-genre 1 --domains '{"element": ["common"], "setting": ["modern"]}'
    """
    import json

    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("SELECT genre FROM new_genre_candidates WHERE id = %s", [candidate_id])
        result = cur.fetchone()

        if not result:
            click.echo(f"候选 ID {candidate_id} 不存在")
            conn.close()
            return

        genre = result[0]

        if domains:
            domains_json = json.loads(domains)
        else:
            domains_json = {"element": ["common"], "setting": ["common"]}

        # 添加到 genre_domain_map
        cur.execute("""
            INSERT INTO genre_domain_map (genre_primary, domains)
            VALUES (%s, %s::jsonb)
            ON CONFLICT (genre_primary) DO UPDATE SET domains = EXCLUDED.domains, updated_at = NOW()
        """, [genre, json.dumps(domains_json)])

        # 更新候选状态
        cur.execute("""
            UPDATE new_genre_candidates
            SET status = 'approved', reviewed_at = NOW()
            WHERE id = %s
        """, [candidate_id])

    conn.close()
    click.echo(f"已批准题材: {genre}")


@cli.command("reject-genre")
@click.argument("candidate_id")
def reject_genre(candidate_id):
    """拒绝新题材。

    示例:
        python review.py reject-genre 1
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE new_genre_candidates
            SET status = 'rejected', reviewed_at = NOW()
            WHERE id = %s
        """, [candidate_id])

    conn.close()
    click.echo(f"已拒绝题材候选 {candidate_id}")


if __name__ == "__main__":
    cli()