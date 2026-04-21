"""Pipeline execution + LLM config management."""

import json
import subprocess
import sys
import yaml
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional

from services import data_service as ds

CONFIG_DIR = ds.DATA_DIR / ".config"
CONFIG_DIR.mkdir(exist_ok=True)
STATUS_FILE = CONFIG_DIR / "pipeline_status.json"
LLM_CONFIG_FILE = CONFIG_DIR / "llm_config.json"
SCRIPTS_DIR = ds.PROJECT_ROOT / "scripts"

MAX_SOURCE_CHARS = 80000


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Status ────────────────────────────────────────────────────────────

def _all_status() -> dict:
    return _read_json(STATUS_FILE)


STALE_TIMEOUT_SECONDS = 600  # 10 min


def get_status(material_id: str) -> dict:
    all_st = _all_status()
    st = all_st.get(material_id, {
        "stages_completed": [],
        "running": False,
        "current_stage": None,
        "last_error": None,
        "updated_at": None,
    })

    if st.get("running") and st.get("updated_at"):
        try:
            updated = datetime.fromisoformat(st["updated_at"])
            elapsed = (datetime.now() - updated).total_seconds()
            if elapsed > STALE_TIMEOUT_SECONDS:
                st["running"] = False
                st["last_error"] = f"任务超时（超过 {int(elapsed)}s 无响应），已自动终止。请重试。"
                st["current_stage"] = None
                all_st[material_id] = st
                _write_json(STATUS_FILE, all_st)
        except (ValueError, TypeError):
            pass

    return st


def reset_status(material_id: str):
    all_st = _all_status()
    cur = all_st.get(material_id, {})
    cur["running"] = False
    cur["current_stage"] = None
    cur["last_error"] = None
    cur["updated_at"] = datetime.now().isoformat()
    all_st[material_id] = cur
    _write_json(STATUS_FILE, all_st)
    return cur


def _set_status(material_id: str, updates: dict):
    all_st = _all_status()
    cur = all_st.get(material_id, {"stages_completed": [], "running": False})
    cur.update(updates)
    cur["updated_at"] = datetime.now().isoformat()
    all_st[material_id] = cur
    _write_json(STATUS_FILE, all_st)


# ── LLM Config ───────────────────────────────────────────────────────

def get_llm_config() -> dict:
    return _read_json(LLM_CONFIG_FILE)


def save_llm_config(cfg: dict):
    existing = get_llm_config()
    existing.update({k: v for k, v in cfg.items() if v is not None})
    _write_json(LLM_CONFIG_FILE, existing)


# ── LLM Call ─────────────────────────────────────────────────────────

def _call_llm(system: str, user: str, temperature: float = 0.3) -> str:
    cfg = get_llm_config()
    base = cfg.get("base_url", "").rstrip("/")
    key = cfg.get("api_key", "")
    model = cfg.get("model", "gpt-4")

    if not base or not key:
        raise RuntimeError("LLM 未配置")

    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }

    with httpx.Client(timeout=300) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM 调用失败 ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("LLM 返回空结果")
    return choices[0].get("message", {}).get("content", "")


def _extract_yaml(text: str) -> str:
    """Extract YAML content from LLM response (may be wrapped in ```yaml blocks)."""
    if "```yaml" in text:
        parts = text.split("```yaml", 1)[1]
        return parts.split("```", 1)[0].strip()
    if "```" in text:
        parts = text.split("```", 1)[1]
        return parts.split("```", 1)[0].strip()
    return text.strip()


def _load_source(material_id: str) -> str:
    nd = ds._novel_dir(material_id)
    formatted = nd / "source_formatted.txt"
    if formatted.exists():
        text = formatted.read_text(encoding="utf-8", errors="replace")
    else:
        sources = list(nd.glob("source.*"))
        if not sources:
            raise FileNotFoundError("No source file")
        text = sources[0].read_text(encoding="utf-8", errors="replace")

    if len(text) > MAX_SOURCE_CHARS:
        head = text[:MAX_SOURCE_CHARS // 2]
        tail = text[-(MAX_SOURCE_CHARS // 2):]
        text = head + f"\n\n... [省略中间部分，全书约{len(text)}字] ...\n\n" + tail
    return text


# ── Stage Execution ──────────────────────────────────────────────────

def run_stage(material_id: str, stage: str):
    _set_status(material_id, {"running": True, "current_stage": stage, "last_error": None})

    try:
        if stage == "ingest":
            _run_ingest(material_id)
        elif stage == "format":
            _run_format(material_id)
        elif stage == "build-index":
            _run_build_index(material_id)
        elif stage == "analyze":
            _run_analyze(material_id)
        elif stage == "events":
            _run_events(material_id)
        elif stage == "finalize":
            _run_finalize(material_id)
        else:
            _set_status(material_id, {"running": False, "last_error": f"Unknown stage: {stage}"})
            return

        status = get_status(material_id)
        completed = list(set(status.get("stages_completed", []) + [stage]))
        _set_status(material_id, {"running": False, "current_stage": None, "stages_completed": completed})

    except Exception as e:
        _set_status(material_id, {"running": False, "current_stage": None, "last_error": str(e)})


def _run_ingest(material_id: str):
    nd = ds._novel_dir(material_id)
    sources = list(nd.glob("source.*"))
    if not sources:
        raise FileNotFoundError(f"No source file in {nd}")


def _run_format(material_id: str):
    format_script = SCRIPTS_DIR / "core" / "source_format.py"
    nd = ds._novel_dir(material_id)
    source = list(nd.glob("source.*"))
    if not source:
        raise FileNotFoundError("No source file found")

    input_path = source[0]
    output_path = nd / "source_formatted.txt"
    report_path = nd / "format_report.yaml"

    if format_script.exists():
        result = subprocess.run(
            [sys.executable, str(format_script), str(input_path), str(output_path), str(report_path)],
            capture_output=True, text=True, cwd=str(ds.PROJECT_ROOT),
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Format script failed: {result.stderr[:500]}")
    else:
        content = input_path.read_text(encoding="utf-8", errors="replace")
        output_path.write_text(content, encoding="utf-8")

    meta = ds._read_yaml(nd / "meta.yaml") or {}
    meta["status"] = "formatted"
    # formatted 字段应在 pipeline 内，而非顶层
    if "pipeline" not in meta:
        meta["pipeline"] = {}
    meta["pipeline"]["formatted"] = True
    meta["pipeline"]["format_date"] = datetime.now().strftime("%Y-%m-%d")
    ds._write_yaml(nd / "meta.yaml", meta)


def _run_build_index(material_id: str):
    build_script = SCRIPTS_DIR / "core" / "build_db.py"
    if not build_script.exists():
        raise FileNotFoundError("build_db.py not found")

    result = subprocess.run(
        [sys.executable, str(build_script)],
        capture_output=True, text=True, cwd=str(ds.PROJECT_ROOT),
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Build index failed: {result.stderr[:500]}")


def _run_events(material_id: str):
    """Event splitting requires Agent — provide guidance rather than auto-run."""
    raise RuntimeError(
        "事件拆分任务过于复杂（需分批处理 + 质量审计循环），"
        "请通过 Agent 执行：/pipeline-events " + material_id
    )


def _run_finalize(material_id: str):
    """Generate stats report from existing event data."""
    cfg = get_llm_config()
    if not cfg.get("base_url") or not cfg.get("api_key"):
        raise RuntimeError("LLM 未配置。请先在设置页面配置 LLM API。")

    nd = ds._novel_dir(material_id)
    meta = ds._read_yaml(nd / "meta.yaml") or {}
    novel_name = meta.get("name", material_id)

    events_dir = nd / "events"
    if not events_dir.exists() or not list(events_dir.glob("ev*.yaml")):
        raise RuntimeError("尚无事件数据，请先执行事件拆分。")

    _set_status(material_id, {"running": True, "current_stage": "finalize:stats"})

    event_summaries = []
    event_files = sorted(events_dir.glob("ev*.yaml"))[:200]
    for ef in event_files:
        event = ds._read_yaml(ef)
        if not event:
            continue
        event_summaries.append(
            f"- {event.get('id','?')}: {event.get('chapter','')} | {event.get('title','')} "
            f"| T{event.get('tension',0)} | {','.join(event.get('event_type',[]))} "
            f"| {','.join(event.get('emotion',[]))}"
        )

    total_events = len(list(events_dir.glob("ev*.yaml")))
    digest = "\n".join(event_summaries)

    system = """你是一位专业的小说数据分析师。根据事件摘要数据生成统计报告。
输出纯 YAML 格式，结构如下：

material_id: <素材ID>
basic:
  total_chapters: <章节数>
  total_events: <事件数>
  avg_events_per_chapter: <平均每章事件数>
pacing:
  avg_tension: <平均张力>
  high_tension_events: <张力>=4的事件数>
  tension_distribution: {1: 数量, 2: 数量, 3: 数量, 4: 数量, 5: 数量}
event_type_distribution:
  - type: <类型>
    count: <数量>
    ratio: <占比>
emotion_distribution:
  - emotion: <情绪>
    count: <数量>
character_stats:
  - name: <人物名>
    event_count: <出场事件数>
technique_stats:
  techniques_used: [技法列表]

基于实际数据统计，不要编造。"""

    user = f"小说《{novel_name}》(ID: {material_id}) 共 {total_events} 个事件。\n\n事件摘要：\n{digest}"
    result = _call_llm(system, user, temperature=0.1)
    parsed = yaml.safe_load(_extract_yaml(result))
    if parsed and isinstance(parsed, dict):
        parsed["material_id"] = material_id
        ds._write_yaml(nd / "stats.yaml", parsed)

    meta["status"] = "complete"
    ds._write_yaml(nd / "meta.yaml", meta)


def _run_analyze(material_id: str):
    """Run LLM-based analysis: outline → worldbuilding → characters → tags."""
    cfg = get_llm_config()
    if not cfg.get("base_url") or not cfg.get("api_key"):
        raise RuntimeError("LLM 未配置。请先在设置页面配置 LLM API。")

    nd = ds._novel_dir(material_id)
    source_text = _load_source(material_id)
    meta = ds._read_yaml(nd / "meta.yaml") or {}
    novel_name = meta.get("name", material_id)

    _set_status(material_id, {"running": True, "current_stage": "analyze:outline"})
    _generate_outline(nd, material_id, novel_name, source_text)

    _set_status(material_id, {"running": True, "current_stage": "analyze:worldbuilding"})
    _generate_worldbuilding(nd, material_id, novel_name, source_text)

    _set_status(material_id, {"running": True, "current_stage": "analyze:characters"})
    _generate_characters(nd, material_id, novel_name, source_text)

    _set_status(material_id, {"running": True, "current_stage": "analyze:tags"})
    _generate_tags(nd, material_id, novel_name, source_text)

    meta["status"] = "outlined"
    ds._write_yaml(nd / "meta.yaml", meta)


def _generate_worldbuilding(nd: Path, material_id: str, name: str, source: str):
    system = """你是一位专业的小说分析师。请从原文中提取世界观设定。
输出纯 YAML 格式（不要 ```yaml 包裹），结构如下：

material_id: <素材ID>
power_system:
  name: <力量体系名称>
  levels: [等级列表]
  rules: <核心规则>
geography:
  - name: <地名>
    description: <描述>
    significance: <叙事意义>
factions:
  - name: <势力名>
    leader: <领袖>
    goal: <目标>
    alignment: <正/中/邪>
background:
  era: <时代背景>
  society: <社会结构>
  key_rules: [世界核心规则列表]

如果某些维度在原文中不存在（如力量体系），可以省略该字段。只提取原文有明确描写的内容。"""

    user = f"小说《{name}》(ID: {material_id}) 的原文如下：\n\n{source}"
    result = _call_llm(system, user)
    parsed = yaml.safe_load(_extract_yaml(result))
    if parsed and isinstance(parsed, dict):
        parsed["material_id"] = material_id
        ds._write_yaml(nd / "worldbuilding.yaml", parsed)


def _generate_outline(nd: Path, material_id: str, name: str, source: str):
    system = """你是一位专业的小说分析师。请分析小说原文，输出故事大纲。
输出纯 YAML 格式（不要 ```yaml 包裹），严格遵循以下结构：

material_id: <素材ID>
premise: <一句话概括故事前提>
theme:
  - <主题1>
  - <主题2>
tone:
  - <基调1>
  - <基调2>
structure:
  - act: <幕名，如"第一幕·起">
    title: <标题>
    chapters: [起始章, 结束章]
    arc: <叙事弧线概述>
    key_event: <关键事件>
    turning_point: <转折点>
    pacing_note: <节奏提示>"""

    user = f"小说《{name}》(ID: {material_id}) 的原文如下：\n\n{source}"
    result = _call_llm(system, user)
    parsed = yaml.safe_load(_extract_yaml(result))
    if parsed and isinstance(parsed, dict):
        parsed["material_id"] = material_id
        ds._write_yaml(nd / "outline.yaml", parsed)


def _generate_characters(nd: Path, material_id: str, name: str, source: str):
    system = """你是一位专业的小说分析师。请从原文中提取人物体系。
输出纯 YAML 格式，结构如下：

material_id: <素材ID>
roster:
  - name: <姓名>
    aliases: [别名列表]
    role: <protagonist/antagonist/supporting/minor>
    first_appearance: <首次出场章节>
    description: <一句话描述>
    traits: [性格特点列表]
    moral_spectrum: <正义/灰色/黑暗>
    archetype: <人物原型>
    narrative_function: <叙事功能>
    arc:
      - stage: <阶段名>
        state: <状态描述>
        trigger: <触发事件>
        chapter: <章节号>

只提取重要人物（出场较多、对剧情有影响的），不超过15人。"""

    user = f"小说《{name}》(ID: {material_id}) 的原文如下：\n\n{source}"
    result = _call_llm(system, user)
    parsed = yaml.safe_load(_extract_yaml(result))
    if parsed and isinstance(parsed, dict):
        parsed["material_id"] = material_id
        ds._write_yaml(nd / "characters.yaml", parsed)


def _generate_tags(nd: Path, material_id: str, name: str, source: str):
    system = """你是一位专业的小说分析师。请为这部小说生成整体标签。
输出纯 YAML 格式，结构如下：

material_id: <素材ID>
genre: [类型，如 都市/玄幻/言情]
sub_genre: [子类型]
theme: [主题列表]
tone: [基调列表]
narrative:
  structure: <单线/多线/网状>
  pov_style: <第一人称/第三人称限制/全知>
  time_handling: <线性/倒叙/插叙>
style:
  prose: [文风，如 朴素/华丽/口语化]
  strength: [写作长板，如 人物塑造/对话/世界观构建]
tropes: [使用的套路/桥段]"""

    user = f"小说《{name}》(ID: {material_id}) 的原文如下：\n\n{source}"
    result = _call_llm(system, user)
    parsed = yaml.safe_load(_extract_yaml(result))
    if parsed and isinstance(parsed, dict):
        parsed["material_id"] = material_id
        ds._write_yaml(nd / "tags.yaml", parsed)
