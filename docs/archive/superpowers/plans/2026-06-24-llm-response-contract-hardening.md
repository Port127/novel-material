# LLM 响应契约统一加固实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为所有 LLM 业务消费点建立显式响应契约，使合法但畸形的 JSON 进入既有容错路径，而不是以未处理的类型异常中断流水线。

**Architecture:** 通用层只提供 `LLMResponseContractError` 和基础类型断言；世界观、章节、大纲、标签、分类、总体评估和人物模块各自定义纯业务契约函数。所有契约验证发生在首次 `.get()`、遍历、落盘或数据库写入之前，并保留现有阶段级、批次级或单项级兜底策略。

**Tech Stack:** Python 3.10+、pytest、现有 OpenAI 兼容 `call_llm()`、YAML、PostgreSQL 标签存储。

---

## 文件结构

### 新建文件

- `src/novel_material/infra/llm_contracts.py`：通用契约异常与基础类型断言，不包含业务字段。
- `tests/infra/test_llm_contracts.py`：通用原语测试。
- `tests/pipeline/test_worldbuilding_contract.py`：世界观归一化与容错测试。
- `tests/pipeline/test_analysis_response_contract.py`：单章响应契约测试。
- `tests/pipeline/test_outline_response_contract.py`：前提、分幕和 beats 契约测试。
- `tests/pipeline/test_tags_response_contract.py`：标签响应契约测试。
- `tests/pipeline/test_evaluate_response_contract.py`：总体评估响应契约测试。
- `tests/pipeline/test_characters_response_contract.py`：人物响应契约测试。

### 修改文件

- `src/novel_material/pipeline/worldbuilding.py`：修正提示词空值契约，验证后再统计和落盘。
- `src/novel_material/pipeline/analyze_validators.py`：增加单章响应纯契约函数。
- `src/novel_material/pipeline/analyze.py`：把契约、质量校验和保存纳入单章错误隔离。
- `src/novel_material/pipeline/outline_logic.py`：验证前提响应并复用默认前提。
- `src/novel_material/pipeline/outline_acts.py`：验证幕和序列结构。
- `src/novel_material/pipeline/outline_beats.py`：验证 beats 结构。
- `src/novel_material/pipeline/tags.py`：数据库连接前验证完整标签响应。
- `src/novel_material/material/classify.py`：补齐 `quality` 嵌套对象和数值契约。
- `src/novel_material/pipeline/evaluate.py`：验证总体评估批次响应。
- `src/novel_material/pipeline/characters_layer.py`：验证人物、关系和关键事件结构。
- `docs/code-review-llm-response-contract-report.md`：实现完成后记录验证结果和解决状态。

---

### Task 1：建立通用 LLM 响应契约原语

**Files:**
- Create: `src/novel_material/infra/llm_contracts.py`
- Create: `tests/infra/test_llm_contracts.py`

- [ ] **Step 1：先写通用原语失败测试**

```python
import pytest

from novel_material.infra.llm_contracts import (
    LLMResponseContractError,
    require_integer,
    require_mapping,
    require_mapping_list,
    require_number,
    require_string,
    require_string_list,
)


def test_require_mapping_reports_field_path_and_actual_type():
    with pytest.raises(
        LLMResponseContractError,
        match=r"worldbuilding\.power_system.*对象.*list",
    ):
        require_mapping([], "worldbuilding.power_system")


def test_require_mapping_list_rejects_non_mapping_item():
    with pytest.raises(LLMResponseContractError, match=r"characters\[1\].*对象"):
        require_mapping_list([{"name": "甲"}, "乙"], "characters")


@pytest.mark.parametrize("value", [True, False])
def test_numeric_contracts_reject_bool(value):
    with pytest.raises(LLMResponseContractError):
        require_number(value, "score")
    with pytest.raises(LLMResponseContractError):
        require_integer(value, "chapter")


def test_string_and_string_list_return_valid_values():
    assert require_string("文本", "summary") == "文本"
    assert require_string_list(["甲", "乙"], "characters") == ["甲", "乙"]
```

- [ ] **Step 2：运行测试并确认因模块不存在而失败**

Run: `pytest -q tests/infra/test_llm_contracts.py`

Expected: FAIL，包含 `ModuleNotFoundError: No module named 'novel_material.infra.llm_contracts'`。

- [ ] **Step 3：实现最小通用原语**

```python
"""LLM 业务响应的基础契约原语。"""

from __future__ import annotations

from typing import Any


class LLMResponseContractError(ValueError):
    """合法 JSON 不符合业务响应契约。"""

    def __init__(self, path: str, expected: str, value: object) -> None:
        self.path = path
        self.expected = expected
        self.actual_type = type(value).__name__
        super().__init__(f"{path} 应为{expected}，实际为 {self.actual_type}")


def require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LLMResponseContractError(path, "对象", value)
    return value


def require_mapping_list(value: object, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LLMResponseContractError(path, "对象数组", value)
    return [require_mapping(item, f"{path}[{index}]") for index, item in enumerate(value)]


def require_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise LLMResponseContractError(path, "字符串", value)
    return value


def require_string_list(value: object, path: str) -> list[str]:
    if not isinstance(value, list):
        raise LLMResponseContractError(path, "字符串数组", value)
    return [require_string(item, f"{path}[{index}]") for index, item in enumerate(value)]


def require_number(value: object, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMResponseContractError(path, "数值", value)
    return value


def require_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LLMResponseContractError(path, "整数", value)
    return value
```

- [ ] **Step 4：运行通用原语测试并确认通过**

Run: `pytest -q tests/infra/test_llm_contracts.py`

Expected: PASS，全部测试通过且无 warning。

- [ ] **Step 5：提交通用契约原语**

```bash
git add src/novel_material/infra/llm_contracts.py tests/infra/test_llm_contracts.py
git commit -m "feat(llm): 增加响应契约基础原语" -m "主要改动：
- 增加统一的 LLMResponseContractError。
- 增加对象、对象数组、字符串、字符串数组、整数和数值断言。

验证结果：
- pytest -q tests/infra/test_llm_contracts.py：通过。"
```

### Task 2：修复世界观响应契约

**Files:**
- Modify: `src/novel_material/pipeline/worldbuilding.py:155-235`
- Create: `tests/pipeline/test_worldbuilding_contract.py`

- [ ] **Step 1：先写世界观空数组和错误类型测试**

```python
import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.worldbuilding import normalize_worldbuilding_response


def test_empty_object_dimensions_are_normalized():
    result = normalize_worldbuilding_response({
        "power_system": [],
        "geography": None,
        "factions": None,
        "lore": {},
    })
    assert result == {
        "power_system": {},
        "geography": {},
        "factions": [],
        "lore": {},
    }


def test_non_empty_power_system_list_is_rejected():
    with pytest.raises(LLMResponseContractError, match="worldbuilding.power_system"):
        normalize_worldbuilding_response({"power_system": [{"name": "修炼"}]})


def test_valid_worldbuilding_response_is_preserved():
    payload = {
        "power_system": {"levels": [{"name": "一级"}]},
        "geography": {"regions": []},
        "factions": [{"name": "组织"}],
        "lore": {"history": []},
    }
    assert normalize_worldbuilding_response(payload) == payload
```

- [ ] **Step 2：运行测试并确认缺少归一化函数**

Run: `pytest -q tests/pipeline/test_worldbuilding_contract.py`

Expected: FAIL，导入 `normalize_worldbuilding_response` 失败。

- [ ] **Step 3：实现纯归一化函数并接入现有容错**

```python
from novel_material.infra.llm_contracts import (
    LLMResponseContractError,
    require_mapping,
    require_mapping_list,
)


def normalize_worldbuilding_response(payload: object) -> dict:
    raw = require_mapping(payload, "worldbuilding")
    result = dict(raw)
    for field in ("power_system", "geography", "lore"):
        value = result.get(field)
        if value is None or value == []:
            result[field] = {}
        else:
            result[field] = require_mapping(value, f"worldbuilding.{field}")
    factions = result.get("factions")
    result["factions"] = [] if factions is None else require_mapping_list(
        factions, "worldbuilding.factions"
    )
    return result
```

将 `call_llm()` 的返回值立即传给该函数，并让 `LLMResponseContractError` 落入当前空结构 `except`。把提示词第 2 条改成：

```text
2. 不存在力量体系、地理或背景知识时，对应字段返回包含空数组的对象或空对象；不存在势力时 factions 返回空数组。字段类型不得改变
```

- [ ] **Step 4：运行世界观测试和原始故障回归测试**

Run: `pytest -q tests/pipeline/test_worldbuilding_contract.py tests/infra/test_llm_contracts.py`

Expected: PASS；`power_system: []` 不再触发 `.get()` 异常。

- [ ] **Step 5：提交世界观修复**

```bash
git add src/novel_material/pipeline/worldbuilding.py tests/pipeline/test_worldbuilding_contract.py
git commit -m "fix(worldbuilding): 校验并归一化 LLM 响应" -m "主要改动：
- 明确世界观各字段的空值类型。
- 在索引和 YAML 写入前校验响应结构。
- 兼容现实题材返回的空数组维度。

验证结果：
- pytest -q tests/pipeline/test_worldbuilding_contract.py tests/infra/test_llm_contracts.py：通过。"
```

### Task 3：隔离单章分析响应结构错误

**Files:**
- Modify: `src/novel_material/pipeline/analyze_validators.py:1-100`
- Modify: `src/novel_material/pipeline/analyze.py:371-452`
- Create: `tests/pipeline/test_analysis_response_contract.py`

- [ ] **Step 1：先写单章字段契约失败测试**

```python
import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.analyze_validators import normalize_chapter_analysis_response


def valid_chapter():
    return {
        "summary": "足够长的章节摘要",
        "characters_appear": ["甲"],
        "chapter_functions": ["人物亮相"],
        "tension_level": 3,
        "pacing": "中",
        "setting": ["办公室"],
        "key_event": "甲作出决定",
        "emotional_tone": ["紧张"],
        "scene_type": ["对话"],
        "technique": [],
        "hook_type": "无钩子",
    }


def test_chapter_response_rejects_top_level_list():
    with pytest.raises(LLMResponseContractError, match="chapter_analysis"):
        normalize_chapter_analysis_response([])


@pytest.mark.parametrize("field,value", [
    ("summary", []),
    ("characters_appear", "甲"),
    ("tension_level", "3"),
    ("emotional_tone", "紧张"),
])
def test_chapter_response_rejects_wrong_field_type(field, value):
    payload = valid_chapter()
    payload[field] = value
    with pytest.raises(LLMResponseContractError, match=field):
        normalize_chapter_analysis_response(payload)
```

- [ ] **Step 2：运行测试并确认缺少契约函数**

Run: `pytest -q tests/pipeline/test_analysis_response_contract.py`

Expected: FAIL，导入 `normalize_chapter_analysis_response` 失败。

- [ ] **Step 3：实现字段契约并扩大单章错误隔离边界**

```python
from novel_material.infra.llm_contracts import (
    LLMResponseContractError,
    require_integer,
    require_mapping,
    require_string,
    require_string_list,
)


def normalize_chapter_analysis_response(payload: object) -> dict:
    result = dict(require_mapping(payload, "chapter_analysis"))
    for field in ("summary", "pacing", "key_event", "hook_type"):
        result[field] = require_string(result.get(field), f"chapter_analysis.{field}")
    for field in (
        "characters_appear", "chapter_functions", "setting",
        "emotional_tone", "scene_type", "technique",
    ):
        result[field] = require_string_list(result.get(field), f"chapter_analysis.{field}")
    tension = require_integer(result.get("tension_level"), "chapter_analysis.tension_level")
    if not 1 <= tension <= 5:
        raise LLMResponseContractError("chapter_analysis.tension_level", "1-5 的整数", tension)
    result["tension_level"] = tension
    for field in ("tension_change", "emotion_transition", "plot_progress"):
        if field in result and result[field] is not None:
            result[field] = require_string(result[field], f"chapter_analysis.{field}")
    return result
```

在 `analyze.py` 中，无论结果来自批量还是单章，都先调用该函数。将契约验证、现有质量验证、元数据补充、pacing 规范化和 `_append_chapter()` 放在同一个 `try` 内；单独捕获 `LLMResponseContractError`，记录 `[schema_invalid]`、增加 `batch_errors` 并 `continue`，不得写入无效章节文件。

- [ ] **Step 4：运行单章契约和现有章节校验测试**

Run: `pytest -q tests/pipeline/test_analysis_response_contract.py tests/validation/test_schema.py`

Expected: PASS；顶层数组与错误字段类型被转换为契约错误。

- [ ] **Step 5：提交单章分析修复**

```bash
git add src/novel_material/pipeline/analyze_validators.py src/novel_material/pipeline/analyze.py tests/pipeline/test_analysis_response_contract.py
git commit -m "fix(analyze): 隔离单章响应契约错误" -m "主要改动：
- 增加单章分析字段级响应契约。
- 将验证、规范化和保存纳入单章错误隔离。
- 禁止畸形响应写入章节 YAML。

验证结果：
- pytest -q tests/pipeline/test_analysis_response_contract.py tests/validation/test_schema.py：通过。"
```

### Task 4：修复大纲前提响应契约

**Files:**
- Modify: `src/novel_material/pipeline/outline_logic.py:43-100`
- Create: `tests/pipeline/test_outline_response_contract.py`

- [ ] **Step 1：先写前提响应与默认值测试**

```python
import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.outline_logic import (
    default_premise_response,
    normalize_premise_response,
)


def test_premise_response_rejects_top_level_list():
    with pytest.raises(LLMResponseContractError, match="outline.premise"):
        normalize_premise_response([])


def test_premise_response_validates_nested_types():
    with pytest.raises(LLMResponseContractError, match="theme"):
        normalize_premise_response({
            "premise": "主角崛起",
            "structure_type": "三幕式",
            "total_acts": 3,
            "theme": "成长",
            "tone": [],
        })


def test_default_premise_is_complete():
    assert default_premise_response() == {
        "premise": "未知",
        "structure_type": "三幕式",
        "total_acts": 3,
        "theme": [],
        "tone": [],
    }
```

- [ ] **Step 2：运行测试并确认新函数不存在**

Run: `pytest -q tests/pipeline/test_outline_response_contract.py`

Expected: FAIL，导入契约函数失败。

- [ ] **Step 3：实现前提契约并让结构错误进入默认兜底**

```python
def default_premise_response() -> dict:
    return {
        "premise": "未知",
        "structure_type": "三幕式",
        "total_acts": 3,
        "theme": [],
        "tone": [],
    }


def normalize_premise_response(payload: object) -> dict:
    result = dict(require_mapping(payload, "outline.premise"))
    result["premise"] = require_string(result.get("premise"), "outline.premise.premise")
    result["structure_type"] = require_string(
        result.get("structure_type"), "outline.premise.structure_type"
    )
    result["total_acts"] = require_integer(result.get("total_acts"), "outline.premise.total_acts")
    if result["total_acts"] < 1:
        raise LLMResponseContractError("outline.premise.total_acts", "正整数", result["total_acts"])
    result["theme"] = require_string_list(result.get("theme"), "outline.premise.theme")
    result["tone"] = require_string_list(result.get("tone"), "outline.premise.tone")
    return result
```

在 `extract_premise()` 的 `try` 内调用 `normalize_premise_response()`；`except` 中统一使用 `default_premise_response()`，并把日志从笼统的调用失败改为包含异常类型的前提提炼失败。

- [ ] **Step 4：运行前提测试**

Run: `pytest -q tests/pipeline/test_outline_response_contract.py`

Expected: PASS；顶层数组会得到契约错误，默认前提完整可保存。

- [ ] **Step 5：提交大纲前提修复**

```bash
git add src/novel_material/pipeline/outline_logic.py tests/pipeline/test_outline_response_contract.py
git commit -m "fix(outline): 校验前提提炼响应" -m "主要改动：
- 增加大纲前提字段契约与默认值工厂。
- 让结构错误复用现有默认前提兜底。

验证结果：
- pytest -q tests/pipeline/test_outline_response_contract.py：通过。"
```

### Task 5：修复标签响应的数据库前置契约

**Files:**
- Modify: `src/novel_material/pipeline/tags.py:31-164,235-324`
- Create: `tests/pipeline/test_tags_response_contract.py`

- [ ] **Step 1：先写标签响应字段类型测试**

```python
import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.tags import default_tags_response, normalize_tags_response


def test_tags_response_rejects_top_level_list():
    with pytest.raises(LLMResponseContractError, match="tags"):
        normalize_tags_response([])


@pytest.mark.parametrize("field,value", [
    ("genre_primary", "都市"),
    ("elements", {"官场": True}),
    ("hooks", 1),
    ("setting", []),
])
def test_tags_response_rejects_wrong_field_type(field, value):
    payload = default_tags_response("都市")
    payload[field] = value
    with pytest.raises(LLMResponseContractError, match=field):
        normalize_tags_response(payload)


def test_default_tags_response_is_valid():
    assert normalize_tags_response(default_tags_response("都市"))["genre_primary"] == ["都市"]
```

- [ ] **Step 2：运行测试并确认契约函数不存在**

Run: `pytest -q tests/pipeline/test_tags_response_contract.py`

Expected: FAIL，导入契约函数失败。

- [ ] **Step 3：实现完整标签契约并在数据库连接前调用**

```python
def default_tags_response(genre_primary: str) -> dict:
    return {
        "genre_primary": [genre_primary],
        "genre_secondary": [],
        "elements": [],
        "setting": None,
        "style": [],
        "structure": None,
        "hooks": [],
        "tropes": [],
        "themes": [],
        "genre_description": "",
    }


def normalize_tags_response(payload: object) -> dict:
    result = dict(require_mapping(payload, "tags"))
    for field in (
        "genre_primary", "genre_secondary", "elements", "style",
        "hooks", "tropes", "themes",
    ):
        result[field] = require_string_list(result.get(field), f"tags.{field}")
    for field in ("setting", "structure"):
        if result.get(field) is not None:
            result[field] = require_string(result[field], f"tags.{field}")
    result["genre_description"] = require_string(
        result.get("genre_description"), "tags.genre_description"
    )
    return result
```

在 `generate_tags()` 的 API `try` 内立即归一化；异常时改用 `normalize_tags_response(default_tags_response(genre_primary))`。确保 `validate_and_save_tags()` 只接收已验证对象，且建立数据库连接之前不再读取未验证字段。

- [ ] **Step 4：运行标签契约测试**

Run: `pytest -q tests/pipeline/test_tags_response_contract.py`

Expected: PASS；畸形响应不会进入数据库校验函数。

- [ ] **Step 5：提交标签修复**

```bash
git add src/novel_material/pipeline/tags.py tests/pipeline/test_tags_response_contract.py
git commit -m "fix(tags): 在数据库写入前校验响应" -m "主要改动：
- 增加标签默认响应与字段级契约。
- 阻止错误集合类型进入候选标签数据库流程。

验证结果：
- pytest -q tests/pipeline/test_tags_response_contract.py：通过。"
```

### Task 6：补齐素材分类嵌套质量契约

**Files:**
- Modify: `src/novel_material/material/classify.py:158-238`
- Modify: `tests/test_classify.py:70-180`

- [ ] **Step 1：先写 `quality` 错误类型回归测试**

```python
from novel_material.infra.llm_contracts import LLMResponseContractError


def test_quality_list_is_reported_as_contract_error():
    genre_mapping = (["其他"], {})
    with pytest.raises(LLMResponseContractError, match="classification.quality"):
        parse_classification_result(
            {"genre_primary": "其他", "quality": []},
            genre_mapping,
        )


@pytest.mark.parametrize("field,value", [
    ("writing", True),
    ("plot", "3"),
    ("character", []),
])
def test_quality_scores_must_be_numbers(field, value):
    genre_mapping = (["其他"], {})
    quality = {"writing": 3, "plot": 3, "character": 3}
    quality[field] = value
    with pytest.raises(LLMResponseContractError, match=field):
        parse_classification_result(
            {"genre_primary": "其他", "quality": quality},
            genre_mapping,
        )
```

- [ ] **Step 2：运行分类定向测试并确认当前出现 AttributeError 或未拒绝**

Run: `pytest -q tests/test_classify.py::TestParseClassificationResult`

Expected: FAIL；`quality: []` 不是 `LLMResponseContractError`，错误分数字段也未被完整拒绝。

- [ ] **Step 3：使用通用原语验证 `quality`**

```python
quality = require_mapping(result.get("quality", {}), "classification.quality")
writing = require_number(quality.get("writing", 3), "classification.quality.writing")
plot = require_number(quality.get("plot", 3), "classification.quality.plot")
character = require_number(
    quality.get("character", 3), "classification.quality.character"
)
quality_score = round((writing + plot + character) / 3, 1)
```

把现有顶层非字典错误也改用 `require_mapping(result, "classification")`。`LLMResponseContractError` 继承 `ValueError`，因此 `classify_book()` 的现有失败结果路径无需扩大捕获范围。

- [ ] **Step 4：运行分类解析测试**

Run: `pytest -q tests/test_classify.py::TestParseClassificationResult`

Expected: PASS；所有分类解析测试通过。

- [ ] **Step 5：提交分类修复**

```bash
git add src/novel_material/material/classify.py tests/test_classify.py
git commit -m "fix(classify): 校验嵌套质量评分结构" -m "主要改动：
- 统一分类顶层对象契约。
- 校验 quality 对象及三个数值评分字段。

验证结果：
- pytest -q tests/test_classify.py::TestParseClassificationResult：通过。"
```

### Task 7：补齐总体评估批次契约

**Files:**
- Modify: `src/novel_material/pipeline/evaluate.py:249-293`
- Create: `tests/pipeline/test_evaluate_response_contract.py`

- [ ] **Step 1：先写总体评估响应契约测试**

```python
import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.evaluate import normalize_evaluation_response


def test_evaluation_response_rejects_top_level_list():
    with pytest.raises(LLMResponseContractError, match="evaluation"):
        normalize_evaluation_response([])


def test_evaluation_response_rejects_string_character_list():
    with pytest.raises(LLMResponseContractError, match="core_characters_hint"):
        normalize_evaluation_response({
            "novel_type": ["都市"],
            "main_thread_summary": "主线",
            "core_characters_hint": "王某",
            "stage_summary": "开篇",
        })


def test_evaluation_response_accepts_standard_shape():
    payload = {
        "novel_type": ["都市"],
        "main_thread_summary": "主线",
        "core_characters_hint": ["王某"],
        "stage_summary": "开篇",
    }
    assert normalize_evaluation_response(payload) == payload
```

- [ ] **Step 2：运行测试并确认函数不存在**

Run: `pytest -q tests/pipeline/test_evaluate_response_contract.py`

Expected: FAIL，导入契约函数失败。

- [ ] **Step 3：实现评估契约并在字段合并前调用**

```python
def normalize_evaluation_response(payload: object) -> dict:
    result = dict(require_mapping(payload, "evaluation"))
    result["novel_type"] = require_string_list(
        result.get("novel_type"), "evaluation.novel_type"
    )
    result["main_thread_summary"] = require_string(
        result.get("main_thread_summary"), "evaluation.main_thread_summary"
    )
    result["core_characters_hint"] = require_string_list(
        result.get("core_characters_hint"), "evaluation.core_characters_hint"
    )
    result["stage_summary"] = require_string(
        result.get("stage_summary"), "evaluation.stage_summary"
    )
    return result
```

在 `evaluate_batch()` 中调用 `call_llm()` 后立即执行该函数，再记录 API 成功和 tokens。让现有 `run_evaluation()` 捕获 `LLMResponseContractError` 并返回 `False`，日志需保留 `schema_invalid` 和字段路径。

- [ ] **Step 4：运行总体评估测试**

Run: `pytest -q tests/pipeline/test_evaluate_response_contract.py`

Expected: PASS；顶层与嵌套错误类型均产生契约错误。

- [ ] **Step 5：提交总体评估修复**

```bash
git add src/novel_material/pipeline/evaluate.py tests/pipeline/test_evaluate_response_contract.py
git commit -m "fix(evaluate): 增加批次响应契约" -m "主要改动：
- 校验总体评估对象、文本和字符串数组字段。
- 区分 schema 错误与 API 调用错误。

验证结果：
- pytest -q tests/pipeline/test_evaluate_response_contract.py：通过。"
```

### Task 8：校验大纲分幕与 beats 兼容形状

**Files:**
- Modify: `src/novel_material/pipeline/outline_acts.py:95-104`
- Modify: `src/novel_material/pipeline/outline_beats.py:92-98`
- Modify: `tests/pipeline/test_outline_response_contract.py`

- [ ] **Step 1：先写裸数组兼容与错误元素测试**

```python
from novel_material.pipeline.outline_acts import normalize_acts_response
from novel_material.pipeline.outline_beats import normalize_beats_response


def test_acts_contract_accepts_wrapped_and_bare_lists():
    acts = [{
        "act_number": 1,
        "name": "第一幕",
        "chapter_start": 1,
        "chapter_end": 10,
        "sequences": [{
            "sequence_number": 1,
            "title": "开篇",
            "chapter_start": 1,
            "chapter_end": 10,
            "description": "建立故事",
        }],
    }]
    assert normalize_acts_response(acts, 10) == acts
    assert normalize_acts_response({"acts": acts}, 10) == acts


def test_acts_contract_rejects_invalid_sequence_item():
    with pytest.raises(LLMResponseContractError, match=r"sequences\[0\]"):
        normalize_acts_response([{
            "act_number": 1,
            "name": "第一幕",
            "chapter_start": 1,
            "chapter_end": 10,
            "sequences": ["开篇"],
        }], 10)


def test_beats_contract_rejects_out_of_range_tension():
    with pytest.raises(LLMResponseContractError, match="tension"):
        normalize_beats_response([{
            "beat_number": 1,
            "title": "转折",
            "chapter": 5,
            "description": "发生转折",
            "tension": 6,
        }], 1, 10)
```

- [ ] **Step 2：运行大纲测试并确认新函数不存在**

Run: `pytest -q tests/pipeline/test_outline_response_contract.py`

Expected: FAIL，导入 `normalize_acts_response` 或 `normalize_beats_response` 失败。

- [ ] **Step 3：实现分幕和 beats 契约**

`normalize_acts_response(payload, chapter_count)` 必须：

```python
raw_acts = payload if isinstance(payload, list) else require_mapping(
    payload, "outline.acts"
).get("acts")
acts = require_mapping_list(raw_acts, "outline.acts")
```

随后逐项验证 `act_number/chapter_start/chapter_end` 为整数、`name` 为字符串、`sequences` 为对象数组；每个 sequence 验证编号、标题、描述和章节范围，并要求 `1 <= start <= end <= chapter_count`。

`normalize_beats_response(payload, seq_start, seq_end)` 同样兼容裸数组和 `{"beats": [...]}`，逐项验证编号、标题、描述、章节号和 `1-5` 张力，并要求章节号位于当前序列范围。

在两个 LLM 调用点用契约函数替换现有仅判断裸数组的分支。现有 `generate_acts_with_fallback()` 和 `generate_all_beats()` 继续负责简单划分与跳过序列。

- [ ] **Step 4：运行全部大纲响应测试**

Run: `pytest -q tests/pipeline/test_outline_response_contract.py`

Expected: PASS；合法裸数组继续工作，错误元素产生字段路径明确的契约错误。

- [ ] **Step 5：提交大纲结构修复**

```bash
git add src/novel_material/pipeline/outline_acts.py src/novel_material/pipeline/outline_beats.py tests/pipeline/test_outline_response_contract.py
git commit -m "fix(outline): 校验分幕与节拍响应结构" -m "主要改动：
- 保留裸数组兼容并增加幕、序列、节拍字段契约。
- 阻止错误元素进入大纲临时文件和最终产物。

验证结果：
- pytest -q tests/pipeline/test_outline_response_contract.py：通过。"
```

### Task 9：校验人物批次响应并保留统计兜底

**Files:**
- Modify: `src/novel_material/pipeline/characters_layer.py:154-183`
- Create: `tests/pipeline/test_characters_response_contract.py`

- [ ] **Step 1：先写人物裸数组、候选名单和嵌套结构测试**

```python
import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.characters_layer import normalize_characters_response


def test_characters_contract_accepts_wrapped_and_bare_lists():
    characters = [{"name": "甲", "relationships": [], "key_events": []}]
    assert normalize_characters_response(characters, {"甲"}) == characters
    assert normalize_characters_response({"characters": characters}, {"甲"}) == characters


def test_characters_contract_rejects_unknown_candidate():
    with pytest.raises(LLMResponseContractError, match="候选名单"):
        normalize_characters_response([{"name": "乙"}], {"甲"})


@pytest.mark.parametrize("field,value", [
    ("relationships", ["朋友"]),
    ("key_events", "第一章"),
])
def test_characters_contract_rejects_invalid_nested_collection(field, value):
    with pytest.raises(LLMResponseContractError, match=field):
        normalize_characters_response([{"name": "甲", field: value}], {"甲"})
```

- [ ] **Step 2：运行测试并确认契约函数不存在**

Run: `pytest -q tests/pipeline/test_characters_response_contract.py`

Expected: FAIL，导入 `normalize_characters_response` 失败。

- [ ] **Step 3：实现人物契约并接入批次 `try`**

```python
def normalize_characters_response(payload: object, candidate_names: set[str]) -> list[dict]:
    raw = payload if isinstance(payload, list) else require_mapping(
        payload, "characters"
    ).get("characters")
    characters = require_mapping_list(raw, "characters")
    for index, character in enumerate(characters):
        name = require_string(character.get("name"), f"characters[{index}].name")
        if name not in candidate_names:
            raise LLMResponseContractError(
                f"characters[{index}].name", "候选名单中的字符串", name
            )
        for field in ("relationships", "key_events"):
            if field in character and character[field] is not None:
                character[field] = require_mapping_list(
                    character[field], f"characters[{index}].{field}"
                )
    return characters
```

在 `_extract_character_batch()` 内先建立 `candidate_names`，调用 `normalize_characters_response()` 后再追加人物。契约错误仍由现有批次 `except` 捕获并为该批全部候选生成统计基础档案，但日志必须标记 `[schema_invalid]`，不能写成 API 调用失败。

- [ ] **Step 4：运行人物响应测试**

Run: `pytest -q tests/pipeline/test_characters_response_contract.py`

Expected: PASS；裸数组和包裹数组兼容，错误人物或嵌套集合触发统计兜底所需的契约错误。

- [ ] **Step 5：提交人物响应修复**

```bash
git add src/novel_material/pipeline/characters_layer.py tests/pipeline/test_characters_response_contract.py
git commit -m "fix(characters): 校验人物批次响应结构" -m "主要改动：
- 校验人物候选名单和嵌套关系、事件数组。
- 保留裸数组兼容与统计基础档案兜底。

验证结果：
- pytest -q tests/pipeline/test_characters_response_contract.py：通过。"
```

### Task 10：完整验证并更新审查结论

**Files:**
- Modify: `docs/code-review-llm-response-contract-report.md`

- [ ] **Step 1：运行全部新增定向测试**

Run:

```bash
pytest -q \
  tests/infra/test_llm_contracts.py \
  tests/pipeline/test_worldbuilding_contract.py \
  tests/pipeline/test_analysis_response_contract.py \
  tests/pipeline/test_outline_response_contract.py \
  tests/pipeline/test_tags_response_contract.py \
  tests/pipeline/test_evaluate_response_contract.py \
  tests/pipeline/test_characters_response_contract.py \
  tests/test_classify.py::TestParseClassificationResult
```

Expected: PASS，0 failed。

- [ ] **Step 2：运行完整测试套件**

Run: `pytest -q`

Expected: PASS，0 failed；允许项目既有的显式 skip。

- [ ] **Step 3：运行编译与格式检查**

Run: `python -m compileall -q src tests`

Expected: exit 0，无输出。

Run: `git diff --check`

Expected: exit 0，无输出。

- [ ] **Step 4：复核所有 LLM 消费点均先经过契约**

Run: `rg -n "call_llm\(" src/novel_material --glob '*.py'`

逐项确认：世界观、章节、大纲前提、标签、分类、总体评估、分幕、beats、人物均在首次读取返回值前调用业务契约；insights、搜索重排、审计复核继续使用现有验证器。把实际测试命令、通过数量和 7 条问题的解决状态写入 `docs/code-review-llm-response-contract-report.md`。

- [ ] **Step 5：提交验证记录**

```bash
git add docs/code-review-llm-response-contract-report.md
git commit -m "docs(llm): 记录响应契约修复验证结果" -m "主要改动：
- 更新五个高风险问题与两个降级诊断问题的解决状态。
- 记录定向测试、完整测试、编译和格式检查结果。

验证结果：
- pytest -q：全部通过。
- python -m compileall -q src tests：通过。
- git diff --check：通过。"
```

## 运行真实素材前的单独门禁

代码和自动化测试完成后，不自动执行真实素材续传。以下命令会调用 LLM、产生 API 消耗并继续写入素材产物，必须再次获得用户明确确认：

```bash
nm pipeline continue nm_novel_20260623_70br --mode standard
```

如果当前非交互 shell 中 `nm` 被系统 `/usr/bin/nm` 覆盖，应在已激活项目 Python 环境后使用项目 console script；不得改为直接调用 `pipeline/*.py`。
