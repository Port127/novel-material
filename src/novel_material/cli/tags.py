"""Tags 子命令：标签管理。"""
import os
import typer
import psycopg2
import psycopg2.extras
from rich.console import Console
from rich.table import Table
from novel_material.runtime.context import run_context
from novel_material.tags.service import TagService

from dotenv import load_dotenv
load_dotenv()

app = typer.Typer(help="标签管理")
console = Console()
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """获取数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


def get_tag_service() -> TagService:
    return TagService(connection_factory=get_connection)


@app.command("stats")
def cmd_stats():
    """显示标签统计。"""
    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT dimension, domain, COUNT(*) as count
            FROM tags GROUP BY dimension, domain ORDER BY dimension, domain
        """)

        table = Table(title="标签统计")
        table.add_column("维度", style="cyan")
        table.add_column("领域", style="green")
        table.add_column("数量", style="yellow")

        for row in cur.fetchall():
            dim, dom, count = row
            table.add_row(dim, dom, str(count))

    # 同义词统计
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tags WHERE synonym_of IS NOT NULL")
        syn_count = cur.fetchone()[0]
        console.print(f"[dim]同义词: {syn_count} 个[/dim]")

    conn.close()
    console.print(table)


@app.command("list")
def cmd_list(
    dimension: str = typer.Option(None, "--dimension", "-d", help="维度筛选"),
    domain: str = typer.Option(None, "--domain", help="领域筛选"),
    limit: int = typer.Option(50, "--limit", "-l", help="显示数量"),
):
    """列出标签。"""
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

        table = Table(title="标签列表")
        table.add_column("维度", style="cyan")
        table.add_column("领域", style="green")
        table.add_column("分组", style="yellow")
        table.add_column("标签", style="white")

        for row in cur.fetchall():
            group = row["group_name"] or "未分组"
            table.add_row(
                row["dimension"],
                row["domain"],
                group,
                row["tag"]
            )

    conn.close()
    console.print(table)


@app.command("add")
def cmd_add(
    dimension: str = typer.Argument(..., help="维度"),
    tag: str = typer.Argument(..., help="标签"),
    domain: str = typer.Argument(..., help="适用领域"),
    group: str = typer.Option(None, "--group", "-g", help="分组"),
    synonym_of: str = typer.Option(None, "--synonym-of", help="同义词指向"),
):
    """添加新标签。"""
    with run_context(command="tags add"):
        get_tag_service().add(
            dimension,
            tag,
            domain,
            group=group,
            synonym_of=synonym_of,
        )
    console.print(f"[green]标签添加成功[/green]: {dimension}/{domain}/{tag}")


@app.command("remove")
def cmd_remove(
    dimension: str = typer.Argument(..., help="维度"),
    tag: str = typer.Argument(..., help="标签"),
):
    """删除标签。"""
    with run_context(command="tags remove"):
        affected = get_tag_service().remove(dimension, tag)
    console.print(f"[green]已删除[/green]: {dimension}/{tag} (影响 {affected} 行)")


@app.command("review")
def cmd_review(
    auto: bool = typer.Option(False, "--auto", "-a", help="自动审批高频标签"),
):
    """审核待定标签候选。"""
    if auto:
        from novel_material.tags.scheduled import auto_approve_by_frequency
        count = auto_approve_by_frequency()
        console.print(f"[green]自动审批了 {count} 个高频标签[/green]")
    else:
        conn = get_connection()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT dimension, tag, occurrence_count, source_material
                FROM new_tag_candidates
                WHERE occurrence_count >= 3
                ORDER BY occurrence_count DESC
                LIMIT 20
            """)
            candidates = cur.fetchall()

        conn.close()

        if not candidates:
            console.print("[yellow]无待审标签[/yellow]")
            return

        table = Table(title="待审标签候选")
        table.add_column("维度", style="cyan")
        table.add_column("标签", style="green")
        table.add_column("出现次数", style="yellow")
        table.add_column("来源", style="dim")

        for c in candidates:
            table.add_row(
                c["dimension"],
                c["tag"],
                str(c["occurrence_count"]),
                c["source_material"] or ""
            )

        console.print(table)


@app.command("move")
def cmd_move(
    dimension: str = typer.Argument(..., help="维度"),
    tag: str = typer.Argument(..., help="标签"),
    new_domain: str = typer.Argument(..., help="新领域"),
):
    """移动标签到其他领域。"""
    with run_context(command="tags move"):
        affected = get_tag_service().move(dimension, tag, new_domain)
    console.print(f"[green]已移动[/green]: {dimension}/{tag} → {new_domain} (影响 {affected} 行)")


@app.command("set-synonym")
def cmd_set_synonym(
    dimension: str = typer.Argument(..., help="维度"),
    tag: str = typer.Argument(..., help="标签"),
    standard_tag: str = typer.Argument(..., help="标准标签"),
):
    """设置同义词关系。"""
    with run_context(command="tags set-synonym"):
        affected = get_tag_service().set_synonym(dimension, tag, standard_tag)
    console.print(f"[green]已设置[/green]: {tag} → {standard_tag} (影响 {affected} 行)")


@app.command("export")
def cmd_export():
    """导出 YAML 视图（人读格式）。"""
    from novel_material.tags.export_view import export_tags_view
    export_tags_view()
    console.print("[green]已导出到[/green] data/tags_view.yaml")


@app.command("info")
def cmd_info(
    dimension: str = typer.Argument(..., help="维度"),
    tag: str = typer.Argument(..., help="标签"),
):
    """查看标签详细信息。"""
    conn = get_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM tags WHERE dimension = %s AND tag = %s
        """, [dimension, tag])
        result = cur.fetchone()

    if not result:
        console.print(f"[red]标签不存在[/red]: {dimension}/{tag}")
        conn.close()
        return

    console.print(f"\n[bold]标签[/bold]: {result['tag']}")
    console.print(f"维度: {result['dimension']}")
    console.print(f"领域: {result['domain']}")
    console.print(f"分组: {result['group_name'] or '未分组'}")
    console.print(f"通用: {result['is_common']}")
    console.print(f"同义词指向: {result['synonym_of'] or '无'}")
    console.print(f"说明: {result['description'] or '无'}")
    console.print(f"创建时间: {result['created_at']}")

    # 查看同义词
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tag FROM tags WHERE synonym_of = %s AND dimension = %s
        """, [tag, dimension])
        synonyms = [row[0] for row in cur.fetchall()]

    if synonyms:
        console.print(f"\n[dim]同义词[/dim]: {', '.join(synonyms)}")

    conn.close()
