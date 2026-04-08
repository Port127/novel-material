"""Centralized data access layer — reads SQLite + YAML, provides clean dicts to routers."""

import sqlite3
import yaml
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "material.db"
NOVELS_DIR = DATA_DIR / "novels"

TAG_DIMENSIONS = [
    "scene_type", "conflict", "stakes",
    "relationship", "interaction", "character_moment",
    "emotion", "reader_effect",
    "plot_function", "plot_stage",
    "technique", "dialogue_type", "info_delivery",
    "setting", "time_weather",
    "pacing", "pov", "power_dynamic", "moral_spectrum", "scale",
]


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _read_yaml(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _write_yaml(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def register_material(material_id: str, name: str, author: str):
    index_path = DATA_DIR / "index.yaml"
    index_data = _read_yaml(index_path) or {"materials": []}
    materials = index_data.get("materials", [])

    for m in materials:
        if m.get("id") == material_id:
            return

    materials.append({
        "id": material_id,
        "type": "novel",
        "name": name,
        "author": author,
        "folder": f"novels/{material_id}",
        "status": "raw",
        "added": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
    })
    index_data["materials"] = materials
    _write_yaml(index_path, index_data)


def _novel_dir(material_id: str) -> Path:
    return NOVELS_DIR / material_id


# ── Materials ──────────────────────────────────────────────────────────


def list_materials() -> list[dict]:
    index_data = _read_yaml(DATA_DIR / "index.yaml")
    if not index_data:
        return []
    materials = index_data.get("materials", [])

    if DB_PATH.exists():
        conn = _get_db()
        for m in materials:
            mid = m.get("id", "")
            row = conn.execute(
                "SELECT total_scenes FROM novels WHERE material_id = ?", (mid,)
            ).fetchone()
            m["scene_count"] = row["total_scenes"] if row else 0
        conn.close()
    else:
        for m in materials:
            m["scene_count"] = 0

    return materials


def get_material(material_id: str) -> Optional[dict]:
    nd = _novel_dir(material_id)
    if not nd.exists():
        return None

    meta = _read_yaml(nd / "meta.yaml") or {}
    meta["material_id"] = material_id

    if DB_PATH.exists():
        conn = _get_db()
        row = conn.execute(
            "SELECT total_scenes FROM novels WHERE material_id = ?", (material_id,)
        ).fetchone()
        meta["scene_count"] = row["total_scenes"] if row else 0
        meta["character_count"] = conn.execute(
            "SELECT COUNT(*) FROM characters WHERE material_id = ?", (material_id,)
        ).fetchone()[0]
        conn.close()

    meta["has_outline"] = (nd / "outline.yaml").exists()
    meta["has_worldbuilding"] = (nd / "worldbuilding.yaml").exists()
    meta["has_characters"] = (nd / "characters.yaml").exists()
    meta["has_tags"] = (nd / "tags.yaml").exists()
    meta["has_stats"] = (nd / "stats.yaml").exists()
    meta["has_scenes"] = (nd / "scenes").is_dir()

    return meta


def get_outline(material_id: str):
    return _read_yaml(_novel_dir(material_id) / "outline.yaml")


def get_worldbuilding(material_id: str):
    return _read_yaml(_novel_dir(material_id) / "worldbuilding.yaml")


def get_characters_yaml(material_id: str):
    return _read_yaml(_novel_dir(material_id) / "characters.yaml")


def get_novel_tags(material_id: str):
    return _read_yaml(_novel_dir(material_id) / "tags.yaml")


def get_stats(material_id: str):
    return _read_yaml(_novel_dir(material_id) / "stats.yaml")


def get_stats_html(material_id: str) -> Optional[str]:
    path = _novel_dir(material_id) / "stats.html"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


# ── Scenes ─────────────────────────────────────────────────────────────


def get_scenes(material_id: str, page: int = 1, limit: int = 50) -> dict:
    if not DB_PATH.exists():
        return {"total": 0, "page": page, "limit": limit, "scenes": []}

    conn = _get_db()
    offset = (page - 1) * limit

    total = conn.execute(
        "SELECT COUNT(*) FROM scenes WHERE material_id = ?", (material_id,)
    ).fetchone()[0]

    rows = conn.execute(
        """SELECT scene_id, chapter, title, summary, tension, pacing,
                  pov, power_dynamic, moral_spectrum, plot_stage, scale
           FROM scenes WHERE material_id = ?
           ORDER BY scene_id LIMIT ? OFFSET ?""",
        (material_id, limit, offset),
    ).fetchall()

    scenes = []
    for row in rows:
        scene = dict(row)
        tags = {}
        for tr in conn.execute(
            "SELECT dimension, value FROM scene_tags WHERE scene_id = ?",
            (row["scene_id"],),
        ):
            tags.setdefault(tr["dimension"], []).append(tr["value"])
        scene["tags"] = tags

        scene["characters"] = [
            cr["character_name"]
            for cr in conn.execute(
                "SELECT character_name FROM scene_characters WHERE scene_id = ?",
                (row["scene_id"],),
            )
        ]
        scenes.append(scene)

    conn.close()
    return {"total": total, "page": page, "limit": limit, "scenes": scenes}


def get_scene_detail(material_id: str, scene_id: str):
    scene_path = _novel_dir(material_id) / "scenes" / f"{scene_id}.yaml"
    if scene_path.exists():
        return _read_yaml(scene_path)

    if not DB_PATH.exists():
        return None
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM scenes WHERE scene_id = ? AND material_id = ?",
        (scene_id, material_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Search ─────────────────────────────────────────────────────────────


def search_scenes(filters: dict) -> dict:
    if not DB_PATH.exists():
        return {"query": filters, "total": 0, "results": [], "relaxed": False}

    conn = _get_db()

    tag_filters = {d: filters[d] for d in TAG_DIMENSIONS if filters.get(d)}
    character_filter = filters.get("character")
    material_filter = filters.get("material")
    tension_min = filters.get("tension_min")
    tension_max = filters.get("tension_max")
    limit = filters.get("limit", 20)

    candidate_sets: list[set] = []

    for dim, val in tag_filters.items():
        ids = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT scene_id FROM scene_tags WHERE dimension=? AND value=?",
                (dim, val),
            )
        }
        candidate_sets.append(ids)

    if character_filter:
        ids = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT scene_id FROM scene_characters WHERE character_name=?",
                (character_filter,),
            )
        }
        candidate_sets.append(ids)

    if material_filter:
        ids = {
            r[0]
            for r in conn.execute(
                "SELECT scene_id FROM scenes WHERE material_id=?", (material_filter,)
            )
        }
        candidate_sets.append(ids)

    result_ids: set[str] = set()
    relaxed = False

    if candidate_sets:
        result_ids = candidate_sets[0]
        for s in candidate_sets[1:]:
            result_ids &= s

    if not result_ids and len(candidate_sets) > 1:
        all_ids: dict[str, int] = {}
        for cs in candidate_sets:
            for sid in cs:
                all_ids[sid] = all_ids.get(sid, 0) + 1
        ranked = sorted(all_ids.items(), key=lambda x: -x[1])
        result_ids = {sid for sid, _ in ranked[: limit * 2]}
        relaxed = True

    if not result_ids:
        conn.close()
        return {"query": _clean_query(filters), "total": 0, "results": [], "relaxed": False}

    ph = ",".join("?" * len(result_ids))
    params: list = list(result_ids)
    sql = f"""
        SELECT s.scene_id, s.material_id, s.chapter, s.title, s.summary,
               s.tension, s.pacing, s.plot_stage, s.power_dynamic, s.scale,
               n.name as novel_name
        FROM scenes s LEFT JOIN novels n ON s.material_id=n.material_id
        WHERE s.scene_id IN ({ph})
    """
    if tension_min is not None:
        sql += " AND s.tension >= ?"
        params.append(tension_min)
    if tension_max is not None:
        sql += " AND s.tension <= ?"
        params.append(tension_max)
    sql += f" ORDER BY s.tension DESC, s.scene_id LIMIT {limit}"

    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        sid = row["scene_id"]
        scene_tags: dict[str, list[str]] = {}
        for tr in conn.execute(
            "SELECT dimension, value FROM scene_tags WHERE scene_id=?", (sid,)
        ):
            scene_tags.setdefault(tr["dimension"], []).append(tr["value"])

        chars = [
            cr[0]
            for cr in conn.execute(
                "SELECT character_name FROM scene_characters WHERE scene_id=?", (sid,)
            )
        ]

        match_count = 0
        matched_dims = []
        for dim, val in tag_filters.items():
            if val in scene_tags.get(dim, []):
                match_count += 1
                matched_dims.append(f"{dim}={val}")
        if character_filter and character_filter in chars:
            match_count += 1
            matched_dims.append(f"character={character_filter}")

        total_f = len(tag_filters) + (1 if character_filter else 0)
        score = round(match_count / total_f, 2) if total_f else 1.0

        results.append(
            {
                "scene_id": sid,
                "material_id": row["material_id"],
                "novel": row["novel_name"] or row["material_id"],
                "chapter": row["chapter"],
                "title": row["title"],
                "summary": row["summary"],
                "tension": row["tension"],
                "characters": chars,
                "tags": scene_tags,
                "matched": matched_dims,
                "score": score,
            }
        )

    results.sort(key=lambda x: (-x["score"], -(x.get("tension") or 0)))
    conn.close()
    return {
        "query": _clean_query(filters),
        "total": len(results),
        "results": results[:limit],
        "relaxed": relaxed,
    }


def search_characters(filters: dict) -> dict:
    if not DB_PATH.exists():
        return {"total": 0, "results": []}

    conn = _get_db()
    conditions, params = [], []

    if filters.get("name"):
        conditions.append("c.name LIKE ?")
        params.append(f"%{filters['name']}%")
    if filters.get("archetype"):
        conditions.append("c.archetype = ?")
        params.append(filters["archetype"])
    if filters.get("role"):
        conditions.append("c.role = ?")
        params.append(filters["role"])
    if filters.get("material"):
        conditions.append("c.material_id = ?")
        params.append(filters["material"])
    if filters.get("moral_spectrum"):
        conditions.append("c.moral_spectrum = ?")
        params.append(filters["moral_spectrum"])

    where = " AND ".join(conditions) if conditions else "1=1"
    limit = filters.get("limit", 20)

    rows = conn.execute(
        f"""SELECT c.*, n.name as novel_name
            FROM characters c LEFT JOIN novels n ON c.material_id=n.material_id
            WHERE {where} LIMIT {limit}""",
        params,
    ).fetchall()

    results = []
    for row in rows:
        item = {
            "name": row["name"],
            "novel": row["novel_name"] or row["material_id"],
            "material_id": row["material_id"],
            "role": row["role"],
            "archetype": row["archetype"],
            "moral_spectrum": row["moral_spectrum"],
            "arc_summary": row["arc_summary"],
            "narrative_function": row["narrative_function"],
        }
        psych = {}
        for f in ("fatal_flaw", "obsession", "soft_spot", "misbelief"):
            if row[f]:
                psych[f] = row[f]
        if psych:
            item["psychology"] = psych

        item["appearance_count"] = conn.execute(
            "SELECT COUNT(*) FROM scene_characters WHERE character_name=?",
            (row["name"],),
        ).fetchone()[0]
        results.append(item)

    conn.close()
    return {"total": len(results), "results": results}


def search_text(query: str, limit: int = 20) -> dict:
    if not DB_PATH.exists():
        return {"query": query, "total": 0, "results": []}

    conn = _get_db()
    rows = conn.execute(
        """SELECT s.scene_id, s.material_id, s.chapter, s.title, s.summary,
                  s.tension, s.plot_stage, n.name as novel_name
           FROM scenes s LEFT JOIN novels n ON s.material_id=n.material_id
           WHERE s.summary LIKE ? OR s.title LIKE ?
           ORDER BY s.scene_id LIMIT ?""",
        (f"%{query}%", f"%{query}%", limit),
    ).fetchall()

    results = [
        {
            "scene_id": r["scene_id"],
            "novel": r["novel_name"] or r["material_id"],
            "material_id": r["material_id"],
            "chapter": r["chapter"],
            "title": r["title"],
            "summary": r["summary"],
            "tension": r["tension"],
        }
        for r in rows
    ]
    conn.close()
    return {"query": query, "total": len(results), "results": results}


# ── Dashboard Stats ────────────────────────────────────────────────────


def get_dashboard_stats() -> dict:
    if not DB_PATH.exists():
        return {"novels": 0, "scenes": 0, "characters": 0, "tag_records": 0}

    conn = _get_db()
    stats: dict = {}

    stats["novels"] = conn.execute("SELECT COUNT(*) FROM novels").fetchone()[0]
    stats["scenes"] = conn.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
    stats["characters"] = conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
    stats["tag_records"] = conn.execute("SELECT COUNT(*) FROM scene_tags").fetchone()[0]

    stats["per_novel"] = [
        {"material_id": r[0], "name": r[1], "scenes": r[2]}
        for r in conn.execute(
            "SELECT material_id, name, total_scenes FROM novels ORDER BY total_scenes DESC"
        )
    ]

    stats["top_scene_types"] = [
        {"value": r[0], "count": r[1]}
        for r in conn.execute(
            "SELECT value, COUNT(*) c FROM scene_tags WHERE dimension='scene_type' GROUP BY value ORDER BY c DESC LIMIT 15"
        )
    ]

    stats["top_emotions"] = [
        {"value": r[0], "count": r[1]}
        for r in conn.execute(
            "SELECT value, COUNT(*) c FROM scene_tags WHERE dimension='emotion' GROUP BY value ORDER BY c DESC LIMIT 15"
        )
    ]

    stats["tension_distribution"] = [
        {"tension": r[0], "count": r[1]}
        for r in conn.execute(
            "SELECT tension, COUNT(*) c FROM scenes WHERE tension>0 GROUP BY tension ORDER BY tension"
        )
    ]

    stats["top_techniques"] = [
        {"value": r[0], "count": r[1]}
        for r in conn.execute(
            "SELECT value, COUNT(*) c FROM scene_tags WHERE dimension='technique' GROUP BY value ORDER BY c DESC LIMIT 10"
        )
    ]

    conn.close()
    return stats


# ── Tag Dictionary ─────────────────────────────────────────────────────


def get_tag_dict():
    return _read_yaml(DATA_DIR / "tags.yaml")


def add_tag_value(dimension: str, value: str) -> dict:
    tags = _read_yaml(DATA_DIR / "tags.yaml")
    if not tags:
        return {"ok": False, "error": "tags.yaml not found"}
    if dimension not in tags:
        return {"ok": False, "error": f"Unknown dimension: {dimension}"}

    dim = tags[dimension]
    values = dim.get("values", [])
    if value in values:
        return {"ok": False, "error": f"Value '{value}' already exists in {dimension}"}

    values.append(value)
    dim["values"] = values
    _write_yaml(DATA_DIR / "tags.yaml", tags)
    return {"ok": True, "dimension": dimension, "value": value}


def merge_tag_values(dimension: str, source: str, target: str) -> dict:
    tags = _read_yaml(DATA_DIR / "tags.yaml")
    if not tags or dimension not in tags:
        return {"ok": False, "error": f"Unknown dimension: {dimension}"}

    dim = tags[dimension]
    values = dim.get("values", [])
    if target not in values:
        return {"ok": False, "error": f"Target '{target}' not in {dimension}"}

    updated = 0
    if DB_PATH.exists():
        conn = _get_db()
        conn.execute(
            "UPDATE scene_tags SET value=? WHERE dimension=? AND value=?",
            (target, dimension, source),
        )
        updated = conn.total_changes
        conn.commit()
        conn.close()

    if source in values:
        values.remove(source)
        dim["values"] = values
        _write_yaml(DATA_DIR / "tags.yaml", tags)

    return {"ok": True, "merged": source, "into": target, "db_updated": updated}


def get_tag_usage() -> dict:
    if not DB_PATH.exists():
        return {}
    conn = _get_db()
    usage: dict[str, list] = {}
    for r in conn.execute(
        "SELECT dimension, value, COUNT(*) c FROM scene_tags GROUP BY dimension, value ORDER BY dimension, c DESC"
    ):
        usage.setdefault(r["dimension"], []).append({"value": r["value"], "count": r["c"]})
    conn.close()
    return usage


# ── Helpers ────────────────────────────────────────────────────────────


def _clean_query(filters: dict) -> dict:
    return {k: v for k, v in filters.items() if v is not None and k != "limit"}
