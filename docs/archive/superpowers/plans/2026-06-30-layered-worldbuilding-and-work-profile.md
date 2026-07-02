# Layered Worldbuilding and Work Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现第三期分层世界观、后置作品画像、审计报告、同步与搜索适配，并保持旧素材可读可查。

**Architecture:** 先新增世界观契约读取层，再让 `worldbuilding` 写入 layered 布局；`profile` 阶段读取既有事实产物生成 `work_profile.yaml`。审计、embedding、storage 和 search 只通过统一读取器消费世界观实体，避免各层重复理解新旧 YAML。

**Tech Stack:** Python 3.12、Typer、Pydantic v2、PyYAML、NumPy、psycopg2、pytest、项目现有 `RunResult/StageResult`、`PipelineOrchestrator`、`audit/reporting/storage/search` 模块。

---

## 执行入口

跨会话执行从：

```text
docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/STATE.md
```

开始。新会话只读取：

1. `AGENTS.md`
2. 上述 `STATE.md`
3. `STATE.md` 指向的当前 packet
4. `git status --short`
5. `git log -3 --oneline`

不要在每次恢复时重读本完整计划，除非当前 packet 明确要求。

## 全局约束

- 不纳入用户原有 `docs/feedback.md` 修改。
- 默认测试不调用真实 LLM、不连接真实数据库、不修改真实素材。
- 真实素材 LLM 重跑或修复必须单独授权。
- 旧世界观四文件只读兼容，不在读取时自动改写。
- 不改变 embedding 维度。
- 未完成人工 Golden Query 前，不声称检索质量提升。
- 每个 packet 必须提交一次代码或文档提交，并更新执行 `STATE.md`。

## 文件结构

新增或修改的核心文件：

```text
src/novel_material/worldbuilding/
├── __init__.py                  # 导出第三期世界观契约与读取器
├── models.py                    # Pydantic 契约模型
├── reader.py                    # 新旧世界观统一读取
├── dimensions.py                # 题材维度路由
├── normalizer.py                # LLM 输出归一化与实体 slug
└── writer.py                    # layered 世界观文件写入

src/novel_material/pipeline/
├── worldbuilding.py             # 改为调用 normalizer/writer，保留 generate_worldbuilding 入口
├── work_profile.py              # 新增 profile 阶段
├── stages.py                    # 新增 run_profile_stage
├── orchestrator.py              # continue 顺序加入 profile
├── progress.py                  # status/legacy inspection 识别 profile
└── stage_contracts.py           # 如需新增 StageResult 适配，保持统一契约

src/novel_material/cli/
├── pipeline.py                  # 新增 nm pipeline profile
└── pipeline_common.py           # full/continue 阶段计划加入 profile

src/novel_material/audit/rules.py            # 新世界观与 work_profile 只读审计
src/novel_material/reporting/models.py       # 如需新增质量摘要字段
src/novel_material/reporting/builder.py      # 聚合新增审计信号
src/novel_material/reporting/markdown.py     # Markdown 展示新增信号

src/novel_material/storage/embedding.py        # 世界观向量化使用统一读取器
src/novel_material/storage/sync_worldbuilding.py# 同步使用统一读取器
src/novel_material/search/world.py             # 返回新 metadata 并保持旧过滤兼容

tests/worldbuilding/
tests/pipeline/
tests/audit/
tests/reporting/
tests/storage/
tests/search/
tests/cli/
tests/validation/
```

---

## Task 1：执行状态目录与 packet 索引

**Files:**
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/README.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/STATE.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-01-state-and-index.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-02-worldbuilding-models-reader.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-03-dimension-router.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-04-normalizer-contract.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-05-layered-writer-pipeline.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-06-audit-report-worldbuilding.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-07-work-profile-contract.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-08-profile-stage-cli.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-09-storage-embedding-sync.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-10-search-world-metadata.md`
- Create: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/task-11-docs-final-verification.md`

- [ ] **Step 1: Verify planning files exist**

Run:

```bash
find docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile -maxdepth 1 -type f | sort
```

Expected: `README.md`、`STATE.md` 和 `task-01` 到 `task-11` 全部存在。

- [ ] **Step 2: Verify no user feedback file is staged**

Run:

```bash
git status --short
```

Expected: `docs/feedback.md` may appear as modified, but it is not staged.

- [ ] **Step 3: Commit planning scaffolding**

```bash
git add docs/superpowers/plans/2026-06-30-layered-worldbuilding-and-work-profile.md docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile
git commit -m "docs(plan): 拆分分层世界观第三期计划" -m "主要改动：
- 新增第三期 implementation plan
- 新增跨会话执行 STATE 与 11 个 packet
- 明确执行入口、验证命令和用户反馈文件隔离

验证结果：
- find execution 目录确认 packet 文件齐全
- git diff --check 通过
- git status --short 确认 docs/feedback.md 未纳入提交"
```

---

## Task 2：世界观契约模型与旧格式兼容读取

**Files:**
- Create: `src/novel_material/worldbuilding/__init__.py`
- Create: `src/novel_material/worldbuilding/models.py`
- Create: `src/novel_material/worldbuilding/reader.py`
- Test: `tests/worldbuilding/test_reader.py`
- Test: `tests/worldbuilding/test_models.py`

- [ ] **Step 1: Write failing model tests**

Add tests that exercise the target contract:

```python
from pathlib import Path

from novel_material.infra.yaml_io import save_yaml
from novel_material.worldbuilding.reader import load_worldbuilding_view


def test_layered_worldbuilding_view_loads_entities_and_relations(tmp_path: Path) -> None:
    wb = tmp_path / "worldbuilding"
    (wb / "entities").mkdir(parents=True)
    save_yaml(wb / "_index.yaml", {
        "schema_version": "2.0.0",
        "layout": "layered",
        "dimension_count": 1,
        "entity_count": 1,
        "relation_count": 1,
        "evidence_count": 1,
        "legacy_compatible": True,
        "llm_success": True,
    })
    save_yaml(wb / "dimensions.yaml", {
        "schema_version": "1.0.0",
        "dimensions": [{
            "id": "business_rules",
            "name": "商业规则",
            "category": "social",
            "applicability": "applicable",
            "reason": "主线围绕创业展开",
            "confidence": 0.8,
        }],
    })
    save_yaml(wb / "overview.yaml", {
        "schema_version": "1.0.0",
        "world_summary": "商业竞争推动剧情",
        "driving_mechanisms": [],
        "confidence": 0.7,
        "limitations": [],
    })
    save_yaml(wb / "entities" / "organization_jiangling_university.yaml", {
        "schema_version": "1.0.0",
        "id": "organization_jiangling_university",
        "type": "organization",
        "name": "江陵大学",
        "description": "主角初始活动环境",
        "importance": "primary",
        "first_appearance_chapter": 1,
        "evidence": [{"chapter": 1, "basis": "fact", "summary": "开篇出现"}],
        "confidence": 0.9,
    })
    save_yaml(wb / "relations.yaml", {
        "schema_version": "1.0.0",
        "relations": [{
            "id": "rel_0001",
            "source_id": "organization_jiangling_university",
            "target_id": "organization_jiangling_university",
            "relation_type": "interacts_with",
            "description": "自引用测试关系",
            "evidence": [{"chapter": 1, "basis": "fact", "summary": "证据"}],
            "confidence": 0.5,
        }],
    })

    view = load_worldbuilding_view(tmp_path)

    assert view.layout == "layered"
    assert [entity.name for entity in view.entities] == ["江陵大学"]
    assert view.relations[0].source_id == "organization_jiangling_university"
    assert view.dimensions[0].applicability == "applicable"


def test_legacy_worldbuilding_view_is_read_without_rewriting(tmp_path: Path) -> None:
    wb = tmp_path / "worldbuilding"
    wb.mkdir()
    save_yaml(wb / "_index.yaml", {
        "power_system_levels": 2,
        "region_count": 1,
        "faction_count": 1,
        "lore_items": 1,
        "llm_success": True,
    })
    save_yaml(wb / "factions.yaml", [{
        "name": "学生会",
        "type": "组织",
        "description": "校园组织",
        "importance": "secondary",
    }])

    before = (wb / "_index.yaml").read_text(encoding="utf-8")
    view = load_worldbuilding_view(tmp_path)
    after = (wb / "_index.yaml").read_text(encoding="utf-8")

    assert view.layout == "legacy"
    assert view.entities[0].name == "学生会"
    assert view.entities[0].type == "factions"
    assert before == after
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/worldbuilding/test_reader.py -v
```

Expected: fail with `ModuleNotFoundError` or missing reader symbols.

- [ ] **Step 3: Implement models and reader**

Create Pydantic models in `models.py`: `WorldbuildingEvidence`、`WorldbuildingDimension`、`WorldbuildingOverview`、`WorldbuildingEntity`、`WorldbuildingRelation`、`WorldbuildingIndex`、`WorldbuildingView` and `LayeredWorldbuilding`.

```python
class WorldbuildingEvidence(BaseModel):
    chapter: int | None = None
    basis: Literal["fact", "inference"] = "fact"
    summary: str = ""


class WorldbuildingEntity(BaseModel):
    schema_version: str = "1.0.0"
    id: str
    type: str
    name: str
    aliases: tuple[str, ...] = ()
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    importance: Literal["primary", "secondary", "minor"] = "secondary"
    first_appearance_chapter: int | None = None
    key_appearances: tuple[dict[str, Any], ...] = ()
    evidence: tuple[WorldbuildingEvidence, ...] = ()
    confidence: float = 0.0
```

`reader.py` exports:

```python
def load_worldbuilding_view(novel_dir: Path) -> WorldbuildingView:
    """Load layered or legacy worldbuilding files into one read-only view."""
```

The reader maps:

- layered `entities/*.yaml` → `WorldbuildingEntity`
- legacy `factions.yaml` → type `factions`
- legacy `geography.yaml` regions → type `regions`
- legacy `power_system.yaml` → type `power_systems`

- [ ] **Step 4: Run focused tests**

```bash
python -m pytest tests/worldbuilding/test_reader.py tests/worldbuilding/test_models.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/novel_material/worldbuilding tests/worldbuilding
git commit -m "feat(worldbuilding): 增加分层世界观读取契约" -m "主要改动：
- 新增世界观 Pydantic 契约模型
- 新增 layered 与 legacy 世界观统一读取器
- 覆盖旧格式只读兼容和 layered 实体关系读取

验证结果：
- python -m pytest tests/worldbuilding/test_reader.py tests/worldbuilding/test_models.py -v：通过"
```

---

## Task 3：题材维度路由

**Files:**
- Create: `src/novel_material/worldbuilding/dimensions.py`
- Test: `tests/worldbuilding/test_dimensions.py`

- [ ] **Step 1: Write failing dimension router tests**

```python
from novel_material.worldbuilding.dimensions import resolve_worldbuilding_dimensions


def test_urban_dimension_router_marks_cultivation_not_applicable() -> None:
    result = resolve_worldbuilding_dimensions(
        meta={"genre": ["都市", "重生"]},
        navigation_dimensions=["商业环境", "校园关系"],
        chapter_signals={"locations": {"江陵大学": 3}, "organizations": {"学生会": 2}},
    )

    by_id = {item.id: item for item in result.dimensions}
    assert by_id["business_rules"].applicability == "applicable"
    assert by_id["cultivation_levels"].applicability == "not_applicable"
    assert "超自然" in by_id["cultivation_levels"].reason


def test_xianxia_dimension_router_keeps_power_and_resources() -> None:
    result = resolve_worldbuilding_dimensions(
        meta={"genre": ["仙侠"]},
        navigation_dimensions=["宗门", "修炼体系"],
        chapter_signals={"locations": {"青云宗": 5}, "organizations": {"青云宗": 5}},
    )

    by_id = {item.id: item for item in result.dimensions}
    assert by_id["cultivation_levels"].applicability == "applicable"
    assert by_id["resources"].applicability == "applicable"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/worldbuilding/test_dimensions.py -v
```

Expected: fail because `dimensions.py` does not exist.

- [ ] **Step 3: Implement router**

Implement:

```python
@dataclass(frozen=True)
class DimensionRoutingResult:
    source: dict[str, object]
    dimensions: tuple[WorldbuildingDimension, ...]


def resolve_worldbuilding_dimensions(
    *,
    meta: dict,
    navigation_dimensions: Iterable[str] = (),
    chapter_signals: dict | None = None,
) -> DimensionRoutingResult:
    ...
```

Genre aliases:

```python
GENRE_PROFILE_ALIASES = {
    "都市": "urban",
    "现实": "urban",
    "重生": "urban",
    "玄幻": "xuanhuan",
    "仙侠": "xianxia",
    "悬疑": "suspense",
}
```

Always include `common`; add profile defaults based on genre and navigation keywords. Include `cultivation_levels` as `not_applicable` for urban/suspense when there is no navigation keyword about 修炼/境界/灵气.

- [ ] **Step 4: Run focused tests**

```bash
python -m pytest tests/worldbuilding/test_dimensions.py tests/pipeline/test_profile_resolver.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/novel_material/worldbuilding/dimensions.py tests/worldbuilding/test_dimensions.py
git commit -m "feat(worldbuilding): 增加题材维度路由" -m "主要改动：
- 新增世界观维度路由器
- 支持 common、urban、xuanhuan、xianxia、suspense 初始维度
- 将不适用维度结构化为 not_applicable

验证结果：
- python -m pytest tests/worldbuilding/test_dimensions.py tests/pipeline/test_profile_resolver.py -v：通过"
```

---

## Task 4：世界观 LLM 输出归一化与契约校验

**Files:**
- Create: `src/novel_material/worldbuilding/normalizer.py`
- Modify: `src/novel_material/pipeline/worldbuilding.py`
- Test: `tests/worldbuilding/test_normalizer.py`
- Test: `tests/pipeline/test_llm_response_contracts.py`

- [ ] **Step 1: Write failing normalizer tests**

```python
import pytest

from novel_material.worldbuilding.normalizer import normalize_layered_worldbuilding_response


def test_normalizer_builds_stable_entity_ids_and_relation_links() -> None:
    result = normalize_layered_worldbuilding_response({
        "overview": {
            "world_summary": "商业竞争推动剧情",
            "driving_mechanisms": [],
            "confidence": 0.8,
            "limitations": [],
        },
        "dimensions": [{
            "id": "business_rules",
            "name": "商业规则",
            "category": "social",
            "applicability": "applicable",
            "reason": "主线围绕创业",
            "confidence": 0.8,
        }],
        "entities": [{
            "type": "organization",
            "name": "江陵大学",
            "description": "主角初始环境",
            "importance": "primary",
            "evidence": [{"chapter": 1, "basis": "fact", "summary": "开篇"}],
            "confidence": 0.9,
        }],
        "relations": [{
            "source": "江陵大学",
            "target": "江陵大学",
            "relation_type": "interacts_with",
            "description": "自引用测试",
            "evidence": [{"chapter": 1, "basis": "fact", "summary": "证据"}],
            "confidence": 0.5,
        }],
    })

    assert result.entities[0].id == "organization_jiangling_university"
    assert result.relations[0].source_id == "organization_jiangling_university"
    assert result.index.entity_count == 1


def test_normalizer_rejects_relation_to_unknown_entity() -> None:
    with pytest.raises(ValueError, match="unknown entity"):
        normalize_layered_worldbuilding_response({
            "overview": {"world_summary": "", "driving_mechanisms": []},
            "dimensions": [],
            "entities": [{"type": "organization", "name": "甲"}],
            "relations": [{"source": "甲", "target": "乙", "relation_type": "conflicts_with"}],
        })
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/worldbuilding/test_normalizer.py -v
```

Expected: fail because normalizer does not exist.

- [ ] **Step 3: Implement normalizer**

Export:

```python
def slugify_entity_id(entity_type: str, name: str) -> str:
    """Return stable ASCII-like id; use pinyin fallback-free hash suffix for Chinese."""


def normalize_layered_worldbuilding_response(payload: object) -> LayeredWorldbuilding:
    """Validate LLM response and return index/overview/dimensions/entities/relations."""
```

ID rule:

- Normalize entity type to lowercase snake case.
- Normalize Chinese or mixed names to `entity_type_` + eight-character SHA-1 suffix when ASCII slug is empty.
- Preserve display name in `name`.

- [ ] **Step 4: Keep legacy contract tests passing**

`pipeline.worldbuilding.normalize_worldbuilding_response` may remain for legacy tests. Add a new wrapper instead of breaking old tests:

```python
def normalize_worldbuilding_response(payload: object) -> dict:
    """Legacy four-file normalization kept for compatibility tests."""
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/worldbuilding/test_normalizer.py tests/pipeline/test_llm_response_contracts.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/novel_material/worldbuilding/normalizer.py src/novel_material/pipeline/worldbuilding.py tests/worldbuilding/test_normalizer.py tests/pipeline/test_llm_response_contracts.py
git commit -m "feat(worldbuilding): 增加分层世界观响应归一化" -m "主要改动：
- 新增 layered 世界观 LLM 响应归一化
- 生成稳定实体 ID 并校验关系引用
- 保留旧世界观响应契约兼容

验证结果：
- python -m pytest tests/worldbuilding/test_normalizer.py tests/pipeline/test_llm_response_contracts.py -v：通过"
```

---

## Task 5：写入 layered `worldbuilding/` 结构并接入 pipeline

**Files:**
- Create: `src/novel_material/worldbuilding/writer.py`
- Modify: `src/novel_material/pipeline/worldbuilding.py`
- Test: `tests/worldbuilding/test_writer.py`
- Test: `tests/pipeline/test_worldbuilding_layered_pipeline.py`

- [ ] **Step 1: Write failing writer tests**

```python
from pathlib import Path

from novel_material.infra.yaml_io import load_yaml
from novel_material.worldbuilding.normalizer import normalize_layered_worldbuilding_response
from novel_material.worldbuilding.writer import write_layered_worldbuilding


def test_write_layered_worldbuilding_outputs_expected_files(tmp_path: Path) -> None:
    layered = normalize_layered_worldbuilding_response({
        "overview": {"world_summary": "校园组织驱动剧情", "driving_mechanisms": []},
        "dimensions": [{
            "id": "organization_network",
            "name": "组织网络",
            "category": "social",
            "applicability": "applicable",
            "reason": "多次出现",
            "confidence": 0.8,
        }],
        "entities": [{
            "type": "organization",
            "name": "学生会",
            "description": "校园组织",
            "importance": "secondary",
            "evidence": [{"chapter": 1, "basis": "fact", "summary": "出现"}],
        }],
        "relations": [],
    })

    write_layered_worldbuilding(tmp_path, layered)

    assert load_yaml(tmp_path / "worldbuilding" / "_index.yaml")["layout"] == "layered"
    assert (tmp_path / "worldbuilding" / "overview.yaml").is_file()
    assert (tmp_path / "worldbuilding" / "dimensions.yaml").is_file()
    assert len(list((tmp_path / "worldbuilding" / "entities").glob("*.yaml"))) == 1
    assert (tmp_path / "worldbuilding" / "relations.yaml").is_file()
```

- [ ] **Step 2: Run writer test to verify failure**

```bash
python -m pytest tests/worldbuilding/test_writer.py -v
```

Expected: fail because writer does not exist.

- [ ] **Step 3: Implement writer**

```python
def write_layered_worldbuilding(novel_dir: Path, layered: LayeredWorldbuilding) -> None:
    wb_dir = novel_dir / "worldbuilding"
    entities_dir = wb_dir / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    save_yaml(wb_dir / "_index.yaml", layered.index.model_dump(mode="json"))
    save_yaml(wb_dir / "overview.yaml", layered.overview.model_dump(mode="json"))
    save_yaml(wb_dir / "dimensions.yaml", {
        "schema_version": "1.0.0",
        "source": layered.dimension_source,
        "dimensions": [item.model_dump(mode="json") for item in layered.dimensions],
    })
    for entity in layered.entities:
        save_yaml(entities_dir / f"{entity.id}.yaml", entity.model_dump(mode="json"))
    save_yaml(wb_dir / "relations.yaml", {
        "schema_version": "1.0.0",
        "relations": [item.model_dump(mode="json") for item in layered.relations],
    })
```

- [ ] **Step 4: Adapt pipeline worldbuilding**

In `generate_worldbuilding`:

- Build dimension routing before prompt.
- Ask LLM for layered shape.
- Normalize with `normalize_layered_worldbuilding_response`.
- Write via `write_layered_worldbuilding`.
- On LLM failure, write layered index with `llm_success: false`, dimensions with routed applicability, empty entities and relations.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/worldbuilding/test_writer.py tests/pipeline/test_worldbuilding_layered_pipeline.py tests/cli/test_pipeline_contract.py::test_remaining_single_stage_failures_exit_one -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/novel_material/worldbuilding/writer.py src/novel_material/pipeline/worldbuilding.py tests/worldbuilding/test_writer.py tests/pipeline/test_worldbuilding_layered_pipeline.py
git commit -m "feat(worldbuilding): 写入分层世界观产物" -m "主要改动：
- 新增 layered 世界观写入器
- worldbuilding 阶段输出 _index、overview、dimensions、entities、relations
- LLM 失败时写入可审计的空 layered 结构

验证结果：
- python -m pytest tests/worldbuilding/test_writer.py tests/pipeline/test_worldbuilding_layered_pipeline.py tests/cli/test_pipeline_contract.py::test_remaining_single_stage_failures_exit_one -v：通过"
```

---

## Task 6：世界观审计与报告质量信号

**Files:**
- Modify: `src/novel_material/audit/rules.py`
- Modify: `src/novel_material/audit/service.py`
- Modify: `src/novel_material/reporting/models.py`
- Modify: `src/novel_material/reporting/builder.py`
- Modify: `src/novel_material/reporting/markdown.py`
- Test: `tests/audit/test_rules.py`
- Test: `tests/audit/test_service.py`
- Test: `tests/reporting/test_builder.py`
- Test: `tests/reporting/test_markdown.py`

- [ ] **Step 1: Write failing audit tests**

Add cases:

```python
from pathlib import Path

from novel_material.audit.models import AuditSeverity
from novel_material.audit.rules import AuditContext, check_worldbuilding
from novel_material.infra.yaml_io import save_yaml


def test_layered_worldbuilding_reports_missing_evidence_and_broken_relation(tmp_path):
    novel = tmp_path
    (novel / "worldbuilding" / "entities").mkdir(parents=True)
    save_yaml(novel / "worldbuilding/_index.yaml", {"layout": "layered", "llm_success": True})
    save_yaml(novel / "worldbuilding/dimensions.yaml", {
        "dimensions": [{"id": "organization_network", "applicability": "applicable"}],
    })
    save_yaml(novel / "worldbuilding/entities/a.yaml", {
        "id": "a",
        "type": "organization",
        "name": "甲组织",
        "importance": "primary",
        "evidence": [],
    })
    save_yaml(novel / "worldbuilding/relations.yaml", {
        "relations": [{"source_id": "a", "target_id": "missing", "relation_type": "conflicts_with"}],
    })

    issues = list(check_worldbuilding(AuditContext("nm_demo", novel)))
    codes = {issue.code for issue in issues}

    assert "worldbuilding_entity_missing_evidence" in codes
    assert "worldbuilding_relation_unknown_entity" in codes
```

- [ ] **Step 2: Run audit tests to verify failure**

```bash
python -m pytest tests/audit/test_rules.py::test_layered_worldbuilding_reports_missing_evidence_and_broken_relation -v
```

Expected: fail because rule does not yet inspect layered structure.

- [ ] **Step 3: Implement audit rules**

In `check_worldbuilding`:

- If index has `layout: layered`, read with `load_worldbuilding_view`.
- Yield `worldbuilding_empty_applicable_dimension` when applicable dimensions exist but no entities and no overview mechanism.
- Yield `worldbuilding_entity_missing_evidence` for primary entities without evidence.
- Yield `worldbuilding_relation_unknown_entity` for relation endpoints not in entity IDs.
- Keep existing legacy warnings unchanged.

- [ ] **Step 4: Add report aggregation**

Expose in report model a worldbuilding summary:

```python
class WorldbuildingQuality(BaseModel):
    layout: str | None = None
    entity_count: int = 0
    relation_count: int = 0
    evidence_count: int = 0
    broken_relation_count: int = 0
    missing_evidence_count: int = 0
```

Builder derives counts from audit issues and `_index.yaml`; Markdown prints one compact row.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/audit tests/reporting -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/novel_material/audit src/novel_material/reporting tests/audit tests/reporting
git commit -m "feat(audit): 增加分层世界观质量信号" -m "主要改动：
- 审计 layered 世界观适用维度、实体证据和关系引用
- 报告展示世界观布局、实体、关系和证据质量摘要
- 保留 legacy 世界观审计语义

验证结果：
- python -m pytest tests/audit tests/reporting -v：通过"
```

---

## Task 7：`work_profile.yaml` 契约

**Files:**
- Create: `src/novel_material/pipeline/work_profile_models.py`
- Create: `src/novel_material/pipeline/work_profile_prompt.py`
- Test: `tests/pipeline/test_work_profile_contract.py`

- [ ] **Step 1: Write failing contract tests**

```python
import pytest

from novel_material.pipeline.work_profile_models import normalize_work_profile_response


def test_normalize_work_profile_requires_evidence_index() -> None:
    profile = normalize_work_profile_response({
        "core_hooks": ["重生后的商业逆袭"],
        "reader_expectations": ["爽点兑现"],
        "story_structure": {"pacing_pattern": "阶段性升级", "turning_point_pattern": []},
        "character_dynamics": {"ensemble_summary": "人物围绕主角事业展开", "key_relationship_patterns": []},
        "worldbuilding_drivers": [{"mechanism": "商业竞争", "narrative_function": "制造选择压力"}],
        "motifs_and_techniques": ["用日常细节塑造人物"],
        "transferable_lessons": [{"lesson": "先给欲望再给阻力", "applies_when": "都市成长线", "avoid_when": "缺少现实规则"}],
        "evidence_index": {"chapters": [1], "characters": ["陈汉升"], "worldbuilding_entities": ["organization_x"]},
        "limitations": [],
        "confidence": 0.8,
    }, material_id="nm_demo", title="示例")

    assert profile.material_id == "nm_demo"
    assert profile.evidence_index.chapters == (1,)


def test_normalize_work_profile_rejects_empty_evidence() -> None:
    with pytest.raises(ValueError, match="evidence_index"):
        normalize_work_profile_response({
            "core_hooks": ["钩子"],
            "reader_expectations": [],
            "story_structure": {},
            "character_dynamics": {},
            "worldbuilding_drivers": [],
            "motifs_and_techniques": [],
            "transferable_lessons": [],
            "evidence_index": {"chapters": [], "characters": [], "worldbuilding_entities": []},
        }, material_id="nm_demo", title="示例")
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/pipeline/test_work_profile_contract.py -v
```

Expected: fail because work profile contract does not exist.

- [ ] **Step 3: Implement contract models**

Implement `WorkProfile`, `StoryStructure`, `CharacterDynamics`, `WorldbuildingDriver`, `TransferableLesson`, `EvidenceIndex` and:

```python
def normalize_work_profile_response(payload: object, *, material_id: str, title: str) -> WorkProfile:
    """Validate LLM work profile response and attach material identity."""
```

Require at least one evidence reference across chapters, characters or worldbuilding entities.

- [ ] **Step 4: Implement prompt builder**

`work_profile_prompt.py` exports:

```python
def build_work_profile_prompt(context: dict) -> tuple[str, str]:
    """Return system and user prompts for work_profile generation."""
```

The prompt states that `work_profile.yaml` is not a fact source and must cite lower-level artifacts in `evidence_index`.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/pipeline/test_work_profile_contract.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/novel_material/pipeline/work_profile_models.py src/novel_material/pipeline/work_profile_prompt.py tests/pipeline/test_work_profile_contract.py
git commit -m "feat(profile): 增加作品画像契约" -m "主要改动：
- 新增 work_profile.yaml Pydantic 契约
- 校验证据索引不能为空
- 新增作品画像提示词构造器

验证结果：
- python -m pytest tests/pipeline/test_work_profile_contract.py -v：通过"
```

---

## Task 8：`profile` 阶段与 CLI/orchestrator/status/continue 接入

**Files:**
- Create: `src/novel_material/pipeline/work_profile.py`
- Modify: `src/novel_material/pipeline/stages.py`
- Modify: `src/novel_material/cli/pipeline.py`
- Modify: `src/novel_material/cli/pipeline_common.py`
- Modify: `src/novel_material/pipeline/orchestrator.py`
- Modify: `src/novel_material/pipeline/progress.py`
- Test: `tests/pipeline/test_work_profile_stage.py`
- Test: `tests/pipeline/test_orchestrator.py`
- Test: `tests/cli/test_pipeline_contract.py`
- Test: `tests/cli/test_command_contracts.py`

- [ ] **Step 1: Write failing stage tests**

```python
from pathlib import Path

from novel_material.infra.yaml_io import load_yaml, save_yaml
from novel_material.pipeline.work_profile import generate_work_profile


def test_generate_work_profile_reads_artifacts_and_writes_yaml(tmp_path: Path, monkeypatch) -> None:
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "name": "示例"})
    save_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "主角创业"}])
    save_yaml(novel / "tags.yaml", {"themes": ["成长"]})
    (novel / "characters" / "profiles").mkdir(parents=True)
    save_yaml(novel / "characters" / "profiles" / "001_主角.yaml", {"name": "主角", "profile_level": "full"})
    (novel / "worldbuilding" / "entities").mkdir(parents=True)
    save_yaml(novel / "worldbuilding" / "_index.yaml", {"layout": "layered", "llm_success": True})
    save_yaml(novel / "worldbuilding" / "entities" / "organization_x.yaml", {
        "id": "organization_x",
        "type": "organization",
        "name": "公司",
        "description": "创业组织",
    })

    monkeypatch.setattr("novel_material.pipeline.work_profile.NOVELS_DIR", tmp_path)
    monkeypatch.setattr("novel_material.pipeline.work_profile.call_llm", lambda *_args, **_kwargs: {
        "core_hooks": ["创业逆袭"],
        "reader_expectations": ["成长爽点"],
        "story_structure": {"pacing_pattern": "阶段推进", "turning_point_pattern": []},
        "character_dynamics": {"ensemble_summary": "围绕创业组队", "key_relationship_patterns": []},
        "worldbuilding_drivers": [{"mechanism": "商业竞争", "narrative_function": "制造压力"}],
        "motifs_and_techniques": ["日常细节"],
        "transferable_lessons": [{"lesson": "用规则制造选择", "applies_when": "现实题材", "avoid_when": "规则缺失"}],
        "evidence_index": {"chapters": [1], "characters": ["主角"], "worldbuilding_entities": ["organization_x"]},
        "limitations": [],
        "confidence": 0.8,
    })

    assert generate_work_profile("nm_demo") is True
    assert load_yaml(novel / "work_profile.yaml")["material_id"] == "nm_demo"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/pipeline/test_work_profile_stage.py -v
```

Expected: fail because `work_profile.py` does not exist.

- [ ] **Step 3: Implement stage**

`work_profile.py` exports:

```python
def generate_work_profile(material_id: str, provider: str | None = None) -> bool:
    """Generate work_profile.yaml from stable artifacts without reading full source text."""
```

It reads existing YAML summaries, limits context to compact snippets, calls LLM once, validates with `normalize_work_profile_response`, writes `work_profile.yaml`, and returns `False` if required base files are missing.

- [ ] **Step 4: Wire CLI and unified pipeline**

Add:

```bash
nm pipeline profile nm_xxx
```

Add `StageSpec("profile", ...)` after `refine` and before `audit` in `_stage_specs`. Enable for `standard/deep`; skip for `fast`.

In `PipelineOrchestrator.plan_continue`, order becomes:

```python
"analyze", "outline", "worldbuilding", "characters", "tags", "insights", "refine", "profile", "audit", "sync"
```

`progress.py` treats `work_profile.yaml` as profile completion.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/pipeline/test_work_profile_stage.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/novel_material/pipeline/work_profile.py src/novel_material/pipeline/stages.py src/novel_material/cli/pipeline.py src/novel_material/cli/pipeline_common.py src/novel_material/pipeline/orchestrator.py src/novel_material/pipeline/progress.py tests/pipeline tests/cli
git commit -m "feat(profile): 接入作品画像流水线阶段" -m "主要改动：
- 新增 profile 阶段生成 work_profile.yaml
- 新增 nm pipeline profile 命令
- full、continue、status 识别 profile 阶段

验证结果：
- python -m pytest tests/pipeline/test_work_profile_stage.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py -v：通过"
```

---

## Task 9：embedding 与 storage 兼容新世界观

**Files:**
- Modify: `src/novel_material/storage/embedding.py`
- Modify: `src/novel_material/storage/sync_worldbuilding.py`
- Test: `tests/storage/test_search_tokens_sync.py`
- Test: `tests/storage/test_worldbuilding_embedding.py`

- [ ] **Step 1: Write failing storage tests**

```python
def test_sync_worldbuilding_reads_layered_entities(tmp_path):
    world_dir = tmp_path / "worldbuilding" / "entities"
    world_dir.mkdir(parents=True)
    save_yaml(tmp_path / "worldbuilding" / "_index.yaml", {"layout": "layered"})
    save_yaml(world_dir / "organization_x.yaml", {
        "id": "organization_x",
        "type": "organization",
        "name": "公司",
        "description": "创业组织",
        "properties": {"dimension_ids": ["business_rules"]},
        "first_appearance_chapter": 3,
        "evidence": [{"chapter": 3, "summary": "成立公司"}],
    })

    connection = RecordingConnection()
    sync_worldbuilding(connection, tmp_path, "nm_demo")

    params = connection.executed[0].params
    assert "organization_x" in params[4]
    assert params[6] == 3
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/storage/test_search_tokens_sync.py::test_sync_worldbuilding_reads_layered_entities -v
```

Expected: fail because sync still reads only old files.

- [ ] **Step 3: Update sync**

Use `load_worldbuilding_view(novel_dir)` in `sync_worldbuilding`. For each entity:

- `entity_type = entity.type`
- `entity_name = entity.name`
- `description = entity.description`
- `properties` includes original `properties`, `entity_id`, `aliases`, `evidence`, `key_appearances`
- `first_appearance = entity.first_appearance_chapter`

Keep legacy vector keys working by checking both `f"{entity.type}:{entity.name}"` and old aliases such as `f"factions:{entity.name}"`.

- [ ] **Step 4: Update embedding**

`embed_worldbuilding` uses `load_worldbuilding_view`. Vector key becomes `f"{entity.type}:{entity.name}"`; text includes name, description, properties and evidence summaries.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/storage/test_search_tokens_sync.py tests/storage/test_worldbuilding_embedding.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/novel_material/storage/embedding.py src/novel_material/storage/sync_worldbuilding.py tests/storage/test_search_tokens_sync.py tests/storage/test_worldbuilding_embedding.py
git commit -m "feat(storage): 兼容分层世界观同步与向量化" -m "主要改动：
- 世界观同步改用统一读取器
- 世界观向量化支持 layered entities
- properties 保留实体 ID、证据和维度信息

验证结果：
- python -m pytest tests/storage/test_search_tokens_sync.py tests/storage/test_worldbuilding_embedding.py -v：通过"
```

---

## Task 10：`search world` 适配新实体 metadata

**Files:**
- Modify: `src/novel_material/search/world.py`
- Modify: `src/novel_material/cli/search.py`
- Test: `tests/search/test_retrievers.py`
- Test: `tests/search/test_contracts.py`
- Test: `tests/cli/test_command_contracts.py`

- [ ] **Step 1: Write failing search metadata test**

```python
def test_world_search_returns_layered_metadata(monkeypatch):
    row = {
        "material_id": "nm_demo",
        "entity_type": "organization",
        "name": "公司",
        "description": "创业组织",
        "properties": {
            "entity_id": "organization_x",
            "dimension_ids": ["business_rules"],
            "evidence": [{"chapter": 3, "summary": "成立公司"}],
            "relation_summaries": ["公司 conflicts_with 对手"],
        },
        "importance": "primary",
        "first_appearance": 3,
        "novel_name": "示例",
        "novel_genre": ["都市"],
    }
    monkeypatch_world_rows([row])

    result = search_worldbuilding(query="公司")[0]

    assert result.metadata["entity_id"] == "organization_x"
    assert result.metadata["dimension_ids"] == ["business_rules"]
    assert result.metadata["evidence"][0]["chapter"] == 3
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/search/test_retrievers.py::test_world_search_returns_layered_metadata -v
```

Expected: fail because metadata does not expose new fields.

- [ ] **Step 3: Implement metadata extraction**

In `search_worldbuilding`, parse `properties` when it is JSON string or dict. Add to metadata:

```python
"entity_id": properties.get("entity_id"),
"dimension_ids": properties.get("dimension_ids", []),
"evidence": properties.get("evidence", []),
"relation_summaries": properties.get("relation_summaries", []),
```

Keep old metadata keys unchanged.

- [ ] **Step 4: Extend entity aliases**

Add aliases:

```python
"organization": "organization",
"location": "location",
"rule": "rule",
"resource": "resource",
"social_system": "social_system",
"history_event": "history_event",
"concept": "concept",
```

Do not remove legacy aliases `factions`、`regions`、`power_systems`.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/search/test_retrievers.py tests/search/test_contracts.py tests/cli/test_command_contracts.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/novel_material/search/world.py src/novel_material/cli/search.py tests/search tests/cli/test_command_contracts.py
git commit -m "feat(search): 适配分层世界观检索元数据" -m "主要改动：
- search world 返回 entity_id、dimension_ids、evidence 和 relation_summaries
- 保持旧世界观过滤别名兼容
- 新增 layered 世界观搜索契约测试

验证结果：
- python -m pytest tests/search/test_retrievers.py tests/search/test_contracts.py tests/cli/test_command_contracts.py -v：通过"
```

---

## Task 11：权威文档、全量验证和真实只读 smoke

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `docs/USER_MANUAL.md`
- Modify: `docs/REQUIREMENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/STATE.md`

- [ ] **Step 1: Update docs**

Document:

- layered worldbuilding directory and schema.
- legacy worldbuilding read compatibility.
- `nm pipeline profile nm_xxx`.
- `work_profile.yaml` role and limits.
- storage/search adaptation without claiming quality improvement.
- real-material LLM rerun requires explicit authorization.

- [ ] **Step 2: Run final verification**

```bash
python -m pytest tests/worldbuilding tests/pipeline tests/audit tests/reporting tests/storage tests/search tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/validation -v
python -m novel_material.cli.main pipeline worldbuilding --help
python -m novel_material.cli.main pipeline profile --help
python -m novel_material.cli.main pipeline full --help
python -m novel_material.cli.main pipeline continue --help
python -m novel_material.cli.main search world --help
python -m compileall -q src/novel_material
python scripts/check_v3_docs.py
git diff --check -- . ':(exclude)docs/feedback.md'
git status --short
```

Expected:

- pytest all pass, 0 failed.
- CLI help shows `profile` command and existing navigation options.
- compileall, docs check and diff check pass.
- `git status --short` contains only planned files plus user `docs/feedback.md`.

- [ ] **Step 3: Real read-only smoke**

If a stable material such as `nm_novel_20260621_4si2` exists locally, run only read-only validation:

```bash
python -m novel_material.cli.main validate artifacts nm_novel_20260621_4si2
```

Expected: exit code may be `0` or `3` depending on known material quality; command must not modify non-report fact files. Do not run real `worldbuilding` or `profile` LLM without explicit user authorization.

- [ ] **Step 4: Mark STATE complete**

Update `STATE.md` and set `last_good_commit` to the short hash of the latest passing code or docs commit:

```yaml
status: complete
current_packet: null
last_completed_packet: task-11-docs-final-verification.md
blocking_issue: null
```

Record final verification command results and known dirty `docs/feedback.md`.

- [ ] **Step 5: Commit docs and state**

```bash
git add ARCHITECTURE.md docs/USER_MANUAL.md docs/REQUIREMENTS.md docs/README.md docs/superpowers/execution/2026-06-30-layered-worldbuilding-and-work-profile/STATE.md
git commit -m "docs(worldbuilding): 完成分层世界观与作品画像文档" -m "主要改动：
- 更新分层世界观、作品画像和 profile 阶段文档
- 记录第三期最终验收结果
- 明确 storage/search 适配不等同于检索质量提升

验证结果：
- 第三期开列 pytest 命令通过
- CLI help、compileall、文档检查和 Git 差异检查通过
- 真实素材只读 smoke 未修改事实文件"
```

---

## 第三期完成门禁

- layered 世界观新写入 `_index.yaml`、`overview.yaml`、`dimensions.yaml`、`entities/*.yaml` 和 `relations.yaml`。
- 旧世界观四文件可继续读取、同步和搜索。
- 不适用维度以 `not_applicable` 结构化表达，不构成质量失败。
- 世界观实体有稳定 ID、描述、重要性、首次出现、证据和置信度。
- 关系引用不存在实体时，审计产生 `worldbuilding_relation_unknown_entity`。
- `work_profile.yaml` 包含作品钩子、读者期待、结构节奏、人物动力、世界观驱动、技法启示、证据索引和限制。
- `nm pipeline profile nm_xxx` 可独立执行。
- `full/continue/status` 识别新增 `profile` 阶段。
- storage/embedding/search 通过统一读取器支持新旧世界观。
- 默认测试无网络、无真实数据库、无真实 LLM。
- 真实素材默认只读验收不修改事实文件。
- 未完成人工 Golden Query 前，文档和报告不声称检索质量提升。
