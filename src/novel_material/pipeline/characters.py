"""人物提取：统计驱动的分层人物提取。

分层策略：
1. 统计章节出场人物频率，筛选候选人（>=5章）
2. 分三层处理：
   - 核心层（>=50章）：完整档案（心理分析、弧线、关键事件）
   - 配角层（>=10章）：标准档案（基础信息 + 关系）
   - 次要层（>=5章）：精简档案（仅基础信息）

注意：此脚本在 analyze 完成后运行，需要 chapters.yaml 作为全书视角输入。
"""
import sys
import yaml
import time
import re
from pathlib import Path
from collections import Counter
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm, get_last_call_finish_reason, get_call_details
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool
from novel_material.infra.progress import get_pipeline_logger, PipelineRunner
from novel_material.storage.embedding import embed_characters

logger = get_pipeline_logger()

# 有效角色类型
VALID_ROLES = ("protagonist", "antagonist", "supporting", "minor")

# 分层阈值（可配置）
CHARACTER_THRESHOLDS = {
    "core": 50,       # >= 50 章为核心人物
    "supporting": 10,  # >= 10 章为配角
    "minor": 5         # >= 5 章为次要人物
}

# 分批大小
CHARACTER_BATCH_SIZE = 25  # 每批处理 25 人


# ============================================================
# 统计驱动的分层筛选
# ============================================================

def _select_candidate_characters(appearance_stats: dict, thresholds: dict | None = None) -> dict:
    """基于出场统计分层筛选候选人。

    Args:
        appearance_stats: 出场统计 {人物名: 出场章数}
        thresholds: 可选的分层阈值，默认使用 CHARACTER_THRESHOLDS

    Returns:
        dict: {
            "core": [(name, count), ...],    # >= 50 章
            "supporting": [...],              # 10-49 章
            "minor": [...]                    # 5-9 章
        }
    """
    if thresholds is None:
        thresholds = CHARACTER_THRESHOLDS

    core_threshold = thresholds.get("core", 50)
    supporting_threshold = thresholds.get("supporting", 10)
    minor_threshold = thresholds.get("minor", 5)

    core = []
    supporting = []
    minor = []

    for name, count in appearance_stats.items():
        if count >= core_threshold:
            core.append((name, count))
        elif count >= supporting_threshold:
            supporting.append((name, count))
        elif count >= minor_threshold:
            minor.append((name, count))

    # 按出场频率排序
    core.sort(key=lambda x: -x[1])
    supporting.sort(key=lambda x: -x[1])
    minor.sort(key=lambda x: -x[1])

    return {
        "core": core,
        "supporting": supporting,
        "minor": minor
    }


def _build_basic_profile_from_stats(name: str, count: int, role: str, chapters_data: list) -> dict:
    """基于出场统计生成基础人物档案（兜底方案，不调用LLM）。

    Args:
        name: 人物名称
        count: 出场章数
        role: 角色类型
        chapters_data: 章节数据（用于提取首章和关键事件）

    Returns:
        dict: 基础人物档案
    """
    # 从章节数据中提取首次出场章节
    first_chapter = None
    key_events = []

    for ch in chapters_data:
        if name in ch.get("characters_appear", []):
            ch_num = ch.get("chapter", 0)
            if first_chapter is None:
                first_chapter = ch_num
            # 收集关键事件（最多5个）
            event = ch.get("key_event", "")
            if event and len(key_events) < 5:
                key_events.append({"chapter": ch_num, "description": event[:30]})

    profile = {
        "name": name,
        "role": role,
        "description": f"出场 {count} 章，为主要角色之一。",
        "first_appearance_chapter": first_chapter,
        "appearance_count": count,
        "narrative_function": "待补充",
        "relationships": []
    }

    if role in ("protagonist", "antagonist", "supporting"):
        # 核心人物添加 key_events
        profile["key_events"] = key_events

    return profile


# ============================================================
# 分批提取人物详情（统计驱动）
# ============================================================

def _extract_character_batch(
    candidates: list[tuple[str, int]],
    role_tier: str,
    context_text: str,
    context_label: str,
    meta: dict,
    config: dict,
    material_id: str = "",
    batch_size: int | None = None,
    chapters_data: list | None = None,
) -> list[dict]:
    """分批调用LLM，为已筛选的候选人补充档案详情。

    注意：候选人名单已由出场统计确定，LLM只需补充详情，不需要"发现"人物。
    若LLM调用失败，使用出场统计生成基础档案兜底。

    Args:
        candidates: 候选人列表 [(name, count), ...]
        role_tier: 角色层级 "core"/"supporting"/"minor"
        context_text: 分析上下文（摘要池）
        context_label: 上下文标签
        meta: 小说元数据
        config: LLM配置
        material_id: 素材ID
        batch_size: 每批处理数量，默认 CHARACTER_BATCH_SIZE
        chapters_data: 章节数据（用于兜底时生成完整档案）

    Returns:
        list[dict]: 人物档案列表
    """
    if not candidates:
        return []

    if batch_size is None:
        batch_size = CHARACTER_BATCH_SIZE

    prefix = f"[{material_id}] " if material_id else ""
    role_mapping = {
        "core": ("protagonist", "antagonist", "supporting"),
        "supporting": ("supporting",),
        "minor": ("minor",)
    }
    valid_roles = role_mapping.get(role_tier, ("minor",))

    # 根据角色层级构建不同的prompt
    if role_tier == "core":
        system_prompt = """你是专业的小说人物分析师。请为以下已确认的核心人物补充完整档案，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名（必须与输入一致）",
      "role": "protagonist/antagonist/supporting",
      "archetype": "英雄/导师/伙伴/反派/隐士/复仇者/守护者/野心家",
      "moral_spectrum": "善良/灰色/邪恶",
      "description": "角色描述（100字）",
      "arc_summary": "角色弧线概述（50字）",
      "narrative_function": "在故事中的功能",
      "psychology": {
        "fatal_flaw": "致命弱点",
        "obsession": "执念/目标",
        "soft_spot": "软肋",
        "motivation": "驱动力"
      },
      "first_appearance_chapter": 1,
      "key_events": [{"chapter": 1, "description": "关键事件"}],
      "relationships": [{"character": "角色名", "relationship": "关系", "nature": "ally/enemy/romance/mentor/rival"}]
    }
  ]
}

注意：
1. 必须为输入名单中的每个角色返回档案，不能遗漏
2. role 根据剧情重要性选择（主角用 protagonist，反派用 antagonist，其他用 supporting）
3. key_events 按重要性排序，最多 10 个
4. relationships 用中文描述"""
    elif role_tier == "supporting":
        system_prompt = """你是专业的小说人物分析师。请为以下已确认的配角补充标准档案，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名（必须与输入一致）",
      "role": "supporting",
      "description": "角色描述（50字）",
      "narrative_function": "在故事中的功能",
      "first_appearance_chapter": 1,
      "key_events": [{"chapter": 1, "description": "关键事件"}],
      "relationships": [{"character": "角色名", "relationship": "关系"}]
    }
  ]
}

注意：
1. 必须为输入名单中的每个角色返回档案，不能遗漏
2. key_events 最多 5 个
3. relationships 用中文描述"""
    else:  # minor
        system_prompt = """你是专业的小说人物分析师。请为以下已确认的次要角色补充精简档案，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名（必须与输入一致）",
      "role": "minor",
      "description": "角色描述（30字）",
      "narrative_function": "在故事中的功能（简述）",
      "first_appearance_chapter": 1,
      "relationships": [{"character": "角色名", "relationship": "关系"}]
    }
  ]
}

注意：
1. 必须为输入名单中的每个角色返回档案，不能遗漏
2. 档案精简，不需要 key_events"""

    all_characters = []
    total_batches = (len(candidates) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(candidates))
        batch_candidates = candidates[batch_start:batch_end]

        # 构建名单文本
        names_list = [f"{name}（{count}章）" for name, count in batch_candidates]
        names_text = "\n".join(names_list)

        user_prompt = f"""请为以下角色补充档案：

类型：{meta.get('theme', ['未知'])}

【待处理角色名单】（共 {len(batch_candidates)} 人）：
{names_text}

{context_label}：
{context_text}

请返回 JSON 格式如上，必须包含名单中每个角色的档案。"""

        try:
            result = call_llm(
                system_prompt, user_prompt, config,
                max_tokens_override=4000,
                timeout_override=config["llm"]["characters_timeout"],
                context=f"{material_id} 人物#{role_tier}批次{batch_idx + 1}"
            )

            if isinstance(result, list):
                characters = result
            else:
                characters = result.get("characters", [])

            # 验证返回的人物是否在候选名单中
            candidate_names = {name for name, _ in batch_candidates}
            for ch in characters:
                ch_name = ch.get("name")
                if ch_name in candidate_names:
                    all_characters.append(ch)
                else:
                    logger.warning(f"{prefix}批次{batch_idx + 1}: LLM返回了非候选人物 '{ch_name}'，跳过")

            logger.info(
                f"{prefix}批次{batch_idx + 1}/{total_batches}: "
                f"返回 {len(characters)} 人，有效 {len([ch for ch in characters if ch.get('name') in candidate_names])} 人"
            )

        except Exception as e:
            logger.error(f"{prefix}批次{batch_idx + 1} LLM调用失败: {e}")
            logger.warning(f"{prefix}使用出场统计生成基础档案兜底")
            # 兜底：生成基础档案
            for name, count in batch_candidates:
                if chapters_data:
                    profile = _build_basic_profile_from_stats(name, count, valid_roles[0], chapters_data)
                else:
                    profile = {
                        "name": name,
                        "role": valid_roles[0],
                        "description": f"出场 {count} 章。",
                        "first_appearance_chapter": None,
                        "narrative_function": "待补充",
                        "appearance_count": count,
                        "relationships": []
                    }
                all_characters.append(profile)

        # 批次间等待（避免rate limit）
        if batch_idx < total_batches - 1:
            time.sleep(config["llm"].get("rate_limit_seconds", 1))

    return all_characters


# ============================================================
# 增量写入辅助函数（断点续传支持）
# ============================================================

def _save_character_profile(profiles_dir: Path, idx: int, profile: dict, name: str) -> None:
    """保存单个人物小传到独立文件（增量写入）。

    Args:
        profiles_dir: profiles 目录路径
        idx: 人物序号
        profile: 人物档案数据
        name: 人物名称（用于生成文件名）
    """
    # slug 化文件名：只保留字母、数字、中文，其他替换为下划线
    slug = re.sub(r'[^\w一-鿿]', '_', name)
    filename = f"{slug}_{idx:03d}.yaml"
    with open(profiles_dir / filename, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)


def _load_existing_profiles(char_dir: Path) -> tuple[list, set]:
    """加载已保存的人物小传（断点续传）。

    Args:
        char_dir: characters 目录路径

    Returns:
        tuple: (已保存的人物档案列表, 已保存的人物名称集合)
    """
    profiles_dir = char_dir / "profiles"
    if not profiles_dir.exists():
        return [], set()

    existing_profiles = []
    existing_names = set()

    for f in profiles_dir.glob("*.yaml"):
        try:
            profile = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            if profile.get("name"):
                existing_profiles.append(profile)
                existing_names.add(profile["name"])
        except Exception:
            continue

    return existing_profiles, existing_names


def _build_profile_from_character(ch: dict, role: str) -> dict:
    """根据角色类型构建人物档案。

    Args:
        ch: LLM 返回的人物数据
        role: 角色类型

    Returns:
        dict: 人物档案
    """
    if role in ("protagonist", "antagonist", "supporting"):
        return {
            "name": ch.get("name"),
            "role": role,
            "archetype": ch.get("archetype"),
            "moral_spectrum": ch.get("moral_spectrum"),
            "description": ch.get("description"),
            "arc_summary": ch.get("arc_summary"),
            "narrative_function": ch.get("narrative_function"),
            "psychology": ch.get("psychology", {}),
            "first_appearance_chapter": ch.get("first_appearance_chapter"),
            "key_events": ch.get("key_events", [])[:10],
            "relationships": ch.get("relationships", [])
        }
    else:
        return {
            "name": ch.get("name"),
            "role": "minor",
            "description": ch.get("description"),
            "first_appearance_chapter": ch.get("first_appearance_chapter"),
            "narrative_function": ch.get("narrative_function"),
            "relationships": ch.get("relationships", [])
        }


def _extract_appearance_stats(chapters_data: list) -> dict:
    """统计章节出场人物频率。

    特殊类型章节（afterword/author_note）不参与统计。

    返回：
        dict: {人物名: 出场章数}
    """
    all_chars = []
    for ch in chapters_data:
        ch_type = ch.get("type", "normal")
        # 跳过特殊类型章节
        if ch_type in ("afterword", "author_note"):
            continue
        chars = ch.get("characters_appear", [])
        all_chars.extend(chars)
    return dict(Counter(all_chars))


def _build_context(novel_dir: Path, config: dict, chapters_data: list | None = None, material_id: str = "") -> tuple[str, str]:
    """构建分析上下文，优先使用章级摘要池，兜底读原文片段。

    章数 > 200 时自动启用分层均匀采样，确保全书首尾及中间均有代表。
    特殊类型章节（afterword/author_note）不参与摘要池构建。

    Args:
        novel_dir: 小说目录
        config: 配置字典
        chapters_data: 可选的已加载章节数据（避免重复调用 load_chapters_data）
    """
    model = config["llm"]["model"]
    if chapters_data is None:
        chapters_data = load_chapters_data(novel_dir)
    if chapters_data:
        # 过滤特殊类型章节（afterword/author_note 不参与人物分析）
        filtered_chapters = [
            ch for ch in chapters_data
            if ch.get("type", "normal") in ("normal", "extra")
        ]
        skipped_count = len(chapters_data) - len(filtered_chapters)

        pool = build_summary_pool(filtered_chapters, config["llm"]["characters_summary_tokens"], model)
        return pool, f"章级摘要池（共 {len(filtered_chapters)} 章，跳过 {skipped_count} 章特殊类型）"

    prefix = f"[{material_id}] " if material_id else ""
    logger.warning(f"{prefix}章节数据不存在或为空，回退到原文前 8000 字（质量受限）")
    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        return f.read()[:8000], "原文摘录（前 8000 字）"


def generate_characters(material_id, progress_callback: Callable[[int, int, str], None] | None = None, provider: str | None = None) -> bool:
    """统计驱动的人物提取。

    新策略：
    1. 基于出场统计筛选候选人（分层：核心/配角/次要）
    2. 分批调用LLM补充档案详情
    3. LLM失败时使用出场统计生成基础档案兜底

    容错策略：任何轮次失败时使用出场统计兜底，不中断流程。
    返回 True 表示成功。

    参数：
        material_id: 素材 ID
        progress_callback: 可选进度回调函数 (done: int, total: int, desc: str) -> None
        provider: 服务商名称（可选，不指定则使用默认配置）
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    config = load_config(provider)
    char_dir = novel_dir / "characters"
    char_dir.mkdir(exist_ok=True)
    profiles_dir = char_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    # 读取 meta
    with open(novel_dir / "meta.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "raw")

    # 读取章节索引获取章数
    chapter_index_file = novel_dir / "chapter_index.yaml"
    chapter_count = 0
    if chapter_index_file.exists():
        with open(chapter_index_file, "r", encoding="utf-8") as f:
            chapter_index = yaml.safe_load(f) or []
            chapter_count = len(chapter_index)

    # 输出小说基本信息
    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}")

    # 创建 PipelineRunner 记录运行历史
    runner = PipelineRunner(
        name="人物提取",
        total_stages=4,  # 核心/配角/次要/向量化
        novel_dir=novel_dir,
        material_id=material_id,
        novel_info={"name": title, "chapter_count": chapter_count, "word_count": word_count}
    )
    wall_start = time.monotonic()

    # 加载章节数据并统计出场人物
    chapters_data = load_chapters_data(novel_dir)
    appearance_stats = _extract_appearance_stats(chapters_data) if chapters_data else {}
    logger.info(f"[{material_id}] 出场人物统计: {len(appearance_stats)} 个不同人物")

    # ── 统计驱动的分层筛选（新增）──
    candidates = _select_candidate_characters(appearance_stats)
    core_candidates = candidates["core"]
    supporting_candidates = candidates["supporting"]
    minor_candidates = candidates["minor"]

    logger.info(
        f"[{material_id}] 分层筛选结果:\n"
        f"  核心人物（>= {CHARACTER_THRESHOLDS['core']} 章）: {len(core_candidates)} 人\n"
        f"  配角（>= {CHARACTER_THRESHOLDS['supporting']} 章）: {len(supporting_candidates)} 人\n"
        f"  次要（>= {CHARACTER_THRESHOLDS['minor']} 章）: {len(minor_candidates)} 人"
    )

    # 构建分析上下文（传递已加载的 chapters_data，避免重复调用）
    context_text, context_label = _build_context(novel_dir, config, chapters_data, material_id=material_id)
    context_chars = len(context_text)
    logger.info(f"[{material_id}] 输入: {context_chars} 字符 | {context_label}")

    # 加载已保存的人物（断点续传）
    existing_profiles, existing_names = _load_existing_profiles(char_dir)
    if existing_profiles:
        logger.info(f"[{material_id}] 断点续传：已保存 {len(existing_profiles)} 个人物")

    # 收集所有关系（后续去重）
    all_relationships = []

    # 收集已有人物的关系（断点续传时避免关系丢失）
    for profile in existing_profiles:
        profile_name = profile.get("name")
        if not profile_name:
            continue
        for rel in profile.get("relationships", []):
            all_relationships.append({
                "from": profile_name,
                "to": rel.get("character"),
                "relationship": rel.get("relationship"),
                "nature": rel.get("nature", "unknown")
            })

    idx = len(existing_profiles)
    total_batches = 3  # 核心/配角/次要 三层

    # ── 第一层：核心人物（>=50章）──
    new_core_count = 0
    core_base_len = len(get_call_details())  # 记录核心阶段开始前的 call_details 基准长度
    if core_candidates:
        if progress_callback:
            progress_callback(0, total_batches, f"提取核心人物 ({len(core_candidates)} 人)")

        try:
            core_characters = _extract_character_batch(
                core_candidates, "core", context_text, context_label,
                meta, config, material_id=material_id, chapters_data=chapters_data
            )
        except Exception as e:
            logger.error(f"[{material_id}] 核心人物提取失败: {e}")
            logger.warning(f"[{material_id}] 使用出场统计生成基础档案兜底")
            core_characters = []
            for name, count in core_candidates:
                profile = _build_basic_profile_from_stats(name, count, "supporting", chapters_data)
                core_characters.append(profile)

        # 保存核心人物
        for ch in core_characters:
            name = ch.get("name")
            if not name or name in existing_names:
                continue

            role = ch.get("role", "supporting")
            if role not in VALID_ROLES:
                role = "supporting"

            profile = _build_profile_from_character(ch, role)
            profile["appearance_count"] = appearance_stats.get(name, 0)
            _save_character_profile(profiles_dir, idx, profile, name)
            existing_profiles.append(profile)
            existing_names.add(name)
            idx += 1
            new_core_count += 1

            for rel in ch.get("relationships", []):
                all_relationships.append({
                    "from": name,
                    "to": rel.get("character"),
                    "relationship": rel.get("relationship"),
                    "nature": rel.get("nature", "unknown")
                })

        logger.info(f"[{material_id}] 核心人物: 保存 {new_core_count} 人")

        # 记录核心人物阶段完成（使用增量计算）
        core_elapsed = time.monotonic() - wall_start
        call_details = get_call_details()
        core_tokens_in = sum(d.get("input_tokens", 0) for d in call_details[core_base_len:])
        core_tokens_out = sum(d.get("output_tokens", 0) for d in call_details[core_base_len:])
        runner.record_stage_complete(
            stage_name=f"核心人物({len(core_candidates)}人)",
            elapsed=core_elapsed,
            api_calls=1,
            api_errors=0 if new_core_count > 0 else 1,
            tokens_in=core_tokens_in,
            tokens_out=core_tokens_out
        )
        wall_start = time.monotonic()
    else:
        logger.info(f"[{material_id}] 无核心人物候选人（>= {CHARACTER_THRESHOLDS['core']} 章）")

    if progress_callback:
        progress_callback(1, total_batches, f"核心人物完成 ({new_core_count} 人)")

    # ── 第二层：配角（10-49章）──
    new_supporting_count = 0
    supporting_base_len = len(get_call_details())  # 记录配角阶段开始前的 call_details 基准长度
    if supporting_candidates:
        if progress_callback:
            progress_callback(1, total_batches, f"提取配角 ({len(supporting_candidates)} 人)")

        try:
            supporting_characters = _extract_character_batch(
                supporting_candidates, "supporting", context_text, context_label,
                meta, config, material_id=material_id, chapters_data=chapters_data
            )
        except Exception as e:
            logger.error(f"[{material_id}] 配角提取失败: {e}")
            logger.warning(f"[{material_id}] 使用出场统计生成基础档案兜底")
            supporting_characters = []
            for name, count in supporting_candidates:
                profile = _build_basic_profile_from_stats(name, count, "supporting", chapters_data)
                supporting_characters.append(profile)

        for ch in supporting_characters:
            name = ch.get("name")
            if not name or name in existing_names:
                continue

            profile = _build_profile_from_character(ch, "supporting")
            profile["appearance_count"] = appearance_stats.get(name, 0)
            _save_character_profile(profiles_dir, idx, profile, name)
            existing_profiles.append(profile)
            existing_names.add(name)
            idx += 1
            new_supporting_count += 1

            for rel in ch.get("relationships", []):
                all_relationships.append({
                    "from": name,
                    "to": rel.get("character"),
                    "relationship": rel.get("relationship"),
                    "nature": rel.get("nature", "unknown")
                })

        logger.info(f"[{material_id}] 配角: 保存 {new_supporting_count} 人")

        # 记录配角阶段完成（使用增量计算）
        supporting_elapsed = time.monotonic() - wall_start
        call_details = get_call_details()
        supporting_tokens_in = sum(d.get("input_tokens", 0) for d in call_details[supporting_base_len:])
        supporting_tokens_out = sum(d.get("output_tokens", 0) for d in call_details[supporting_base_len:])
        runner.record_stage_complete(
            stage_name=f"配角({len(supporting_candidates)}人)",
            elapsed=supporting_elapsed,
            api_calls=1,
            api_errors=0 if new_supporting_count > 0 else 1,
            tokens_in=supporting_tokens_in,
            tokens_out=supporting_tokens_out
        )
        wall_start = time.monotonic()
    else:
        logger.info(f"[{material_id}] 无配角候选人（>= {CHARACTER_THRESHOLDS['supporting']} 章）")

    if progress_callback:
        progress_callback(2, total_batches, f"配角完成 ({new_supporting_count} 人)")

    # ── 第三层：次要人物（5-9章）──
    new_minor_count = 0
    minor_base_len = len(get_call_details())  # 记录次要阶段开始前的 call_details 基准长度
    if minor_candidates:
        if progress_callback:
            progress_callback(2, total_batches, f"提取次要人物 ({len(minor_candidates)} 人)")

        try:
            minor_characters = _extract_character_batch(
                minor_candidates, "minor", context_text, context_label,
                meta, config, material_id=material_id, chapters_data=chapters_data
            )
        except Exception as e:
            logger.error(f"[{material_id}] 次要人物提取失败: {e}")
            logger.warning(f"[{material_id}] 使用出场统计生成基础档案兜底")
            minor_characters = []
            for name, count in minor_candidates:
                profile = _build_basic_profile_from_stats(name, count, "minor", chapters_data)
                minor_characters.append(profile)

        for ch in minor_characters:
            name = ch.get("name")
            if not name or name in existing_names:
                continue

            profile = _build_profile_from_character(ch, "minor")
            profile["appearance_count"] = appearance_stats.get(name, 0)
            _save_character_profile(profiles_dir, idx, profile, name)
            existing_profiles.append(profile)
            existing_names.add(name)
            idx += 1
            new_minor_count += 1

            for rel in ch.get("relationships", []):
                all_relationships.append({
                    "from": name,
                    "to": rel.get("character"),
                    "relationship": rel.get("relationship"),
                    "nature": rel.get("nature", "unknown")
                })

        logger.info(f"[{material_id}] 次要人物: 保存 {new_minor_count} 人")

        # 记录次要人物阶段完成（使用增量计算）
        minor_elapsed = time.monotonic() - wall_start
        call_details = get_call_details()
        minor_tokens_in = sum(d.get("input_tokens", 0) for d in call_details[minor_base_len:])
        minor_tokens_out = sum(d.get("output_tokens", 0) for d in call_details[minor_base_len:])
        runner.record_stage_complete(
            stage_name=f"次要人物({len(minor_candidates)}人)",
            elapsed=minor_elapsed,
            api_calls=1,
            api_errors=0 if new_minor_count > 0 else 1,
            tokens_in=minor_tokens_in,
            tokens_out=minor_tokens_out
        )
    else:
        logger.info(f"[{material_id}] 无次要人物候选人（>= {CHARACTER_THRESHOLDS['minor']} 章）")

    if progress_callback:
        progress_callback(3, total_batches, f"完成: {new_core_count + new_supporting_count + new_minor_count} 人")

    # 合并所有人物（现有 + 新增）
    all_characters = existing_profiles

    # 关系去重：按人物对去重（A-B 和 B-A 视为同一对）
    seen_pairs = set()
    unique_relationships = []
    for rel in all_relationships:
        if not rel.get("from") or not rel.get("to"):
            continue
        pair_key = tuple(sorted([rel["from"], rel["to"]]))
        if pair_key not in seen_pairs:
            seen_pairs.add(pair_key)
            unique_relationships.append(rel)

    # 写入人物索引
    char_index = {
        "character_count": len(all_characters),
        "protagonist_count": sum(1 for c in all_characters if c.get("role") == "protagonist"),
        "antagonist_count": sum(1 for c in all_characters if c.get("role") == "antagonist"),
        "supporting_count": sum(1 for c in all_characters if c.get("role") == "supporting"),
        "minor_count": sum(1 for c in all_characters if c.get("role") == "minor"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    with open(char_dir / "_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(char_index, f, allow_unicode=True, default_flow_style=False)

    # 写入关系网
    with open(char_dir / "relationships.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"relationships": unique_relationships}, f, allow_unicode=True, default_flow_style=False)

    logger.info(
        f"[{material_id}] 人物提取完成:\n"
        f"  总人物: {char_index['character_count']}\n"
        f"  主角: {char_index['protagonist_count']}\n"
        f"  反派: {char_index['antagonist_count']}\n"
        f"  配角: {char_index['supporting_count']}\n"
        f"  次要: {char_index['minor_count']}\n"
        f"  关系: {len(unique_relationships)} 条"
    )

    # 保存运行历史
    runner.save_history(status="success")

    # 生成人物向量
    logger.info(f"[{material_id}] 生成人物向量...")
    if progress_callback:
        progress_callback(3, 4, "生成人物向量...")
    embed_characters(material_id)
    if progress_callback:
        progress_callback(4, 4, "向量化完成")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python characters.py <material_id>")
        sys.exit(1)

    generate_characters(sys.argv[1])