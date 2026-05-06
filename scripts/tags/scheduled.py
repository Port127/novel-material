#!/usr/bin/env python
"""定时批处理：频率自动批、LLM辅助批量审核。

分级审核策略：
- Level 1: element/style 维度，出现 ≥3 次自动批准
- Level 2: setting/structure 维度，LLM辅助批量审核
"""
import os
import sys
import json
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


def auto_approve_by_frequency():
    """频率自动批：element 和 style 维度，出现 ≥3 次自动入库。

    Level 1 审核策略。

    Returns:
        int: 自动批准的标签数量
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # 查询出现 ≥3 次的候选
        cur.execute("""
            SELECT id, dimension, tag, context_genre, suggested_domain, occurrence_count
            FROM new_tag_candidates
            WHERE status = 'pending'
              AND dimension IN ('element', 'style')
              AND occurrence_count >= 3
            ORDER BY occurrence_count DESC
        """)
        candidates = cur.fetchall()

    approved_count = 0

    for c in candidates:
        # 根据题材推断领域
        domain = infer_domain(c["context_genre"], c["dimension"]) or c["suggested_domain"] or "common"

        with conn.cursor() as cur:
            # 自动入库
            cur.execute("""
                INSERT INTO tags (dimension, tag, domain, is_common)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dimension, tag) DO NOTHING
            """, [c["dimension"], c["tag"], domain, domain == "common"])

            # 更新候选状态
            cur.execute("""
                UPDATE new_tag_candidates
                SET status = 'auto_approved', reviewed_at = NOW(), reviewed_by = 'auto_frequency'
                WHERE id = %s
            """, [c["id"]])

        approved_count += 1

    conn.close()

    print(f"频率自动批准了 {approved_count} 个标签")
    return approved_count


def llm_batch_review():
    """LLM辅助批量审核：setting 和 structure 维度。

    Level 2 审核策略。

    Returns:
        int: 处理的标签数量
    """
    conn = get_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # 查询待审核候选
        cur.execute("""
            SELECT id, dimension, tag, context_genre, suggested_domain, source_material, occurrence_count
            FROM new_tag_candidates
            WHERE status = 'pending' AND dimension IN ('setting', 'structure')
            ORDER BY occurrence_count DESC LIMIT 50
        """)
        candidates = cur.fetchall()

    if not candidates:
        print("没有待 LLM 审核的标签")
        conn.close()
        return 0

    # 构建 LLM prompt
    prompt = build_llm_review_prompt(candidates)

    # TODO: 调用 LLM（需要实现）
    # 这里暂时跳过 LLM 调用，需要用户手动审核
    print(f"发现 {len(candidates)} 个待 LLM 审核的标签（setting/structure 维度）")
    print("请使用以下命令手动审核:")
    print("  python scripts/tags/review.py list --dimension setting")
    print("  python scripts/tags/review.py approve <id> --domain cultivation")

    conn.close()
    return 0


def build_llm_review_prompt(candidates):
    """构建 LLM 审核 prompt。"""
    lines = ["以下是一些新标签候选，请判断是否应该加入字典：\n"]

    for c in candidates:
        lines.append(f"- {c['dimension']}/{c['tag']}")
        lines.append(f"  来源题材: {c['context_genre']}")
        lines.append(f"  建议领域: {c['suggested_domain'] or '未指定'}")
        lines.append(f"  出现次数: {c['occurrence_count']}")
        lines.append("")

    lines.append("""
请返回 JSON 格式：
{
  "reviews": [
    {"tag": "xxx", "action": "approve", "domain": "cultivation", "reason": "..."},
    {"tag": "yyy", "action": "reject", "reason": "..."},
    ...
  ]
}
""")

    return "\n".join(lines)


def infer_domain(genre, dimension):
    """根据题材推断标签领域。"""
    if not genre:
        return None

    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT domains FROM genre_domain_map WHERE genre_primary = %s
        """, [genre])
        result = cur.fetchone()

    conn.close()

    if result and dimension in result[0]:
        domains = result[0][dimension]
        # 返回第一个非 common 的领域
        for d in domains:
            if d != "common":
                return d

    return None


def update_free_tags_stats():
    """分析自由标签统计，发现高频词建议升级。"""
    conn = get_connection()

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT dimension, tag, occurrence_count
            FROM free_tags_stats
            WHERE occurrence_count >= 10
            ORDER BY occurrence_count DESC
        """)
        stats = cur.fetchall()

    conn.close()

    if stats:
        print("\n高频自由标签（建议考虑升级为正式标签）:")
        for s in stats:
            print(f"  {s['dimension']}/{s['tag']}: {s['occurrence_count']} 次")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python scheduled.py auto-approve    # 频率自动批")
        print("  python scheduled.py llm-review      # LLM辅助批量审核（待实现）")
        print("  python scheduled.py stats           # 分析自由标签")
        sys.exit(1)

    if sys.argv[1] == "auto-approve":
        auto_approve_by_frequency()
    elif sys.argv[1] == "llm-review":
        llm_batch_review()
    elif sys.argv[1] == "stats":
        update_free_tags_stats()
    else:
        print(f"未知命令: {sys.argv[1]}")