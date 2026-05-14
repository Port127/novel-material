# 25-05-14-plan-classify-refactor.md

# 素材分类功能重构执行计划

## 执行原则

- 敢于删除，但要精准定位（grep 内容特征）
- 改完验证，失败就修，不回退
- 不留尾巴（兼容层、过渡函数）

---

## 批次规划

```
批次1 → 批次2 → 批次3 → 批次4
(标签对接) (取样策略) (信息扩展) (清理验证)

依赖关系：
- 批次2 依赖批次1（取样策略需使用新 genre）
- 批次3 依赖批次2（信息提取依赖新取样内容）
- 批次4 依赖批次1-3（清理需等核心功能稳定）
```

---

## 批次1：标签对接

**目标**：使用系统标签体系，分类结果可入库

### 步骤1：新建 genre 映射函数

**文件**：`material/classify.py`

```python
# 新建函数（在文件末尾）
def load_genre_mapping():
    """从数据库加载 genre 映射，返回一级和二级题材列表。"""
    from novel_material.tags.load import get_all_genres, infer_primary_from_secondary
    
    # 一级题材（用于匹配）
    primary_genres = get_all_genres()
    
    # 二级题材映射（用于归一化）
    return primary_genres, infer_primary_from_secondary
```

### 步骤2：修改提示词

**文件**：`material/classify_prompt.py`

**删除**：硬编码的 `VALID_GENRES` 和 `SYSTEM_PROMPT` 中的 genre 列表

**新建**：动态生成提示词函数

```python
# 新建函数
def build_classify_prompt(genre_list):
    """动态构建分类提示词，genre_list 来自系统标签体系。"""
    
    genre_text = "\n".join(f"- {g}" for g in genre_list[:20])  # 取前 20 个一级题材
    
    SYSTEM_PROMPT = f"""你是小说类型分类专家。根据小说样本内容，判断其 genre 类型。

输出格式（JSON）：
{
  "genre_primary": "一级题材",
  "genre_secondary": "二级题材（可选）",
  "genre_description": "一句话描述小说类型特点",
  "confidence": 0.8
}

一级题材取值范围：
{genre_text}

选择规则：
1. 必须选择一个一级题材
2. 二级题材可选，但需与一级题材匹配
3. confidence 表示分类置信度（0.0-1.0）"""

    return SYSTEM_PROMPT
```

### 步骤3：修改 classify_book 函数

**文件**：`material/classify.py:145-200`

```python
# 修改前（硬编码）
result = call_llm(
    system_prompt=SYSTEM_PROMPT,
    user_prompt=user_prompt,
    config=config,
)

# 修改后（动态）
primary_genres, secondary_mapping = load_genre_mapping()
system_prompt = build_classify_prompt(primary_genres)

result = call_llm(
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    config=config,
)
```

### 步骤4：修改结果解析

**文件**：`material/classify.py:101-140`

```python
# 修改前
genre = result.get("genre")
for g in genre:
    if g in VALID_GENRES:  # 硬编码校验

# 修改后
genre_primary = result.get("genre_primary")
genre_secondary = result.get("genre_secondary")

# 使用 tags 模块校验
from novel_material.tags.validate import validate_tag
valid_primary = validate_tag("genre", genre_primary)  # 返回归一化名称

# 二级题材归一化到一级
if genre_secondary:
    inferred = secondary_mapping.get(genre_secondary)
    if inferred and inferred != genre_primary:
        # 提示二级题材属于不同一级
        logger.warning(f"二级题材 {genre_secondary} 映射到 {inferred}，与 {genre_primary} 不同")
```

### 步骤5：修改输出格式

**文件**：`material/classify.py` 返回值

```python
# 修改前
return {
    "genre": ["仙侠", "修仙"],
    "genre_description": "...",
    "confidence": 0.95,
    "status": "done",
}

# 修改后
return {
    "genre_primary": "仙侠",
    "genre_secondary": "修真文明",
    "genre_description": "...",
    "confidence": 0.95,
    "status": "done",
}
```

### 步骤6：修改 CLI 保存格式

**文件**：`cli/material.py:214-225`

```python
# 修改保存格式
material_index["materials"][key] = {
    ...
    "genre_primary": result["genre_primary"],
    "genre_secondary": result.get("genre_secondary", ""),
    # 保留兼容字段
    "genre": [result["genre_primary"], result.get("genre_secondary", "")],
    ...
}
```

### 步骤7：验证

```bash
# 测试 genre 对接
nm material classify clean --yes
nm material classify start --limit 5

# 检查输出
cat data/material_index.yaml | grep genre
# 应输出：genre_primary: 仙侠，genre_secondary: 修真文明
```

### 步骤8：删除

| 序号 | 文件路径 | 内容特征 | 删除条件 |
|------|----------|---------|---------|
| 1 | `classify_prompt.py:38-55` | `VALID_GENRES = {` | 匹配则删除整个常量定义 |
| 2 | `classify_prompt.py:15-25` | `genre 取值范围：` 在 SYSTEM_PROMPT 中 | 替换为动态生成 |

---

## 批次2：取样策略

**目标**：分布式采样约 0.5% 章节（最少 3 章，最多 10 章）

### 步骤1：新建取样函数

**文件**：`material/classify.py`

```python
# 新建函数（替换 extract_first_three_chapters）
def extract_sample_chapters(
    file_path: Path,
    total_chapters: int = None,
    sample_ratio: float = 0.005,
    min_chapters: int = 3,
    max_chapters: int = 30,  # 用户指定最多 30 章
    max_chars_per_chapter: int = 1500,  # 减少每章字符，控制总量
) -> str:
    """分布式采样章节内容。

    采样分布：
    - 开头：1 章（了解设定）
    - 中间：按比例分配
    - 后期：1 章（了解结局/转折）

    Args:
        file_path: 小说文件路径
        total_chapters: 总章数（可选，自动检测）
        sample_ratio: 采样比例（默认 0.5%）
        min_chapters: 最少采样章数
        max_chapters: 最多采样章数
        max_chars_per_chapter: 每章最多字符

    Returns:
        str: 采样内容（章节标题 + 内容）
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 章节检测
    chapter_pattern = re.compile(
        r"(?:^|\n)(第[一二三四五六七八九十百千万零\d]+章|第\d+章)",
        re.MULTILINE
    )
    matches = list(chapter_pattern.finditer(content))
    
    if len(matches) < min_chapters:
        # 少于最少章数，取全文前 max_chars
        return content[:min_chapters * max_chars_per_chapter]

    # 计算采样数量
    n_chapters = len(matches)
    sample_count = max(
        min_chapters,
        min(max_chapters, int(n_chapters * sample_ratio))
    )

    # 分布采样位置
    positions = []
    
    # 开头：第 1 章
    positions.append(0)
    
    # 中间：均匀分布
    if sample_count > 2:
        mid_count = sample_count - 2  # 减去开头和结尾
        mid_positions = [
            int(n_chapters * (i + 1) / (mid_count + 1))
            for i in range(mid_count)
        ]
        positions.extend(mid_positions)
    
    # 结尾：最后一章
    if sample_count > 1:
        positions.append(n_chapters - 1)

    # 提取章节内容
    samples = []
    for pos in positions:
        if pos >= len(matches):
            continue
        
        start = matches[pos].start()
        if content[start] == '\n':
            start += 1
        
        # 结束位置：下一章开始或文件末尾
        end_pos = matches[pos + 1].start() if pos + 1 < len(matches) else len(content)
        
        chapter_content = content[start:end_pos]
        if len(chapter_content) > max_chars_per_chapter:
            chapter_content = chapter_content[:max_chars_per_chapter]
        
        samples.append(chapter_content)

    return "\n\n---\n\n".join(samples)
```

### 步骤2：修改 classify_book 调用

**文件**：`material/classify.py:170`

```python
# 修改前
content = extract_first_three_chapters(file_path)

# 修改后
content = extract_sample_chapters(file_path)
```

### 步骤3：修改提示词模板

**文件**：`classify_prompt.py`

```python
USER_PROMPT_TEMPLATE = """小说标题：{title}
作者：{author}

采样章节内容（开头 + 中间 + 后期）：
{content}

请根据以上样本内容分析并输出分类结果。
注意：样本可能包含开头设定、中间发展和后期转折，综合判断题材。"""
```

### 步骤4：验证

```bash
# 测试取样
nm material classify clean --yes
nm material classify start --limit 3

# 检查日志中的 token 消耗
# 应约为：input 8000-10000, output 2500-3000
```

### 步骤5：删除

| 序号 | 文件路径 | 内容特征 | 删除条件 |
|------|----------|---------|---------|
| 1 | `classify.py:40-98` | `def extract_first_three_chapters` | 整个函数删除 |

---

## 批次3：信息扩展

**目标**：一次调用提取 genre + element + style + quality + priority

### 步骤1：扩展提示词输出格式

**文件**：`classify_prompt.py`

```python
SYSTEM_PROMPT = """你是小说分析专家。根据小说样本内容，提取以下信息：

输出格式（JSON）：
{
  "genre_primary": "一级题材",
  "genre_secondary": "二级题材",
  "genre_description": "题材描述",
  
  "elements": ["核心元素1", "核心元素2"],
  "elements_description": "元素特点描述",
  
  "style": {
    "narrative": "叙事风格",
    "tone": "情感基调",
    "pace": "节奏类型"
  },
  
  "quality": {
    "writing": "文笔评分（1-5）",
    "plot": "剧情评分（1-5）",
    "character": "人物评分（1-5）"
  },
  
  "confidence": 0.8
}

输出规则：
1. elements 取 3-5 个最核心的元素（如：重生、系统、逆袭）
2. style 各字段取值需符合常见分类
3. quality 评分基于文笔、剧情逻辑、人物塑造"""
```

### 步骤2：新建结果解析函数

**文件**：`material/classify.py`

```python
def parse_extended_result(result: dict, genre_mapping: tuple) -> dict:
    """解析扩展的分类结果。"""
    
    # Genre 解析（使用批次1的校验逻辑）
    genre_primary = result.get("genre_primary", "其他")
    genre_secondary = result.get("genre_secondary", "")
    
    # Elements 解析
    elements = result.get("elements", [])
    if not isinstance(elements, list):
        elements = []
    
    # Style 解析
    style = result.get("style", {})
    
    # Quality 解析
    quality = result.get("quality", {})
    writing = quality.get("writing", 3)
    plot = quality.get("plot", 3)
    character = quality.get("character", 3)
    
    # 综合评分（用于排序）
    quality_score = (writing + plot + character) / 3
    
    return {
        "genre_primary": genre_primary,
        "genre_secondary": genre_secondary,
        "genre_description": result.get("genre_description", ""),
        "elements": elements,
        "elements_description": result.get("elements_description", ""),
        "style": style,
        "quality": {
            "writing": writing,
            "plot": plot,
            "character": character,
            "score": round(quality_score, 1),
        },
        "confidence": result.get("confidence", 0.5),
    }
```

### 步骤3：修改 classify_book 返回

**文件**：`material/classify.py`

```python
# 修改返回值
return parse_extended_result(result, (primary_genres, secondary_mapping))
```

### 步骤4：修改 CLI 保存格式

**文件**：`cli/material.py`

```python
material_index["materials"][key] = {
    "title": title,
    "author": author,
    "file_path": str(file_path),
    "file_size": novel.get("file_size", 0),
    "download_count": novel.get("download_count", 0),
    
    # Genre（批次1）
    "genre_primary": result["genre_primary"],
    "genre_secondary": result.get("genre_secondary", ""),
    "genre_description": result.get("genre_description", ""),
    
    # Elements（批次3新增）
    "elements": result.get("elements", []),
    "elements_description": result.get("elements_description", ""),
    
    # Style（批次3新增）
    "style": result.get("style", {}),
    
    # Quality（批次3新增）
    "quality": result.get("quality", {}),
    
    # Meta
    "classification_status": result["status"],
    "classification_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "confidence": result.get("confidence", 0.0),
}
```

### 步骤5：验证

```bash
nm material classify clean --yes
nm material classify start --limit 5

# 检查输出格式
cat data/material_index.yaml
# 应包含：elements, style, quality, priority 等字段
```

---

## 批次4：清理验证

**目标**：删除废弃代码，更新测试和文档

### 步骤1：删除废弃函数

| 序号 | 文件路径 | 内容特征 | 删除条件 |
|------|----------|---------|---------|
| 1 | `classify.py` | `def parse_classification_result` | 替换为 `parse_extended_result` 后删除 |

### 步骤2：更新测试

**文件**：`tests/test_classify.py`

```python
# 新增测试
class TestExtractSampleChapters:
    def test_sample_distribution(self, temp_novel_dir):
        """测试采样分布。"""
        # 创建 100 章小说
        content = "\n\n".join(f"第{i}章 内容{i}" for i in range(1, 101))
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)
        
        result = extract_sample_chapters(test_file)
        
        # 应采样约 5 章（100 * 0.005 = 0.5, min=3, max=10 → 5）
        assert "第1章" in result  # 开头
        assert "第100章" in result  # 结尾
    
    def test_short_novel(self, temp_novel_dir):
        """少于 3 章时取全文。"""
        content = "第1章 内容\n\n第2章 内容"
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)
        
        result = extract_sample_chapters(test_file)
        
        assert len(result) > 0


class TestExtendedResult:
    def test_parse_elements(self):
        """测试元素解析。"""
        result = {
            "genre_primary": "玄幻",
            "elements": ["重生", "系统", "逆袭"],
            "quality": {"writing": 4, "plot": 3, "character": 3},
            "priority": {"入库优先级": "high"},
        }
        
        parsed = parse_extended_result(result, ...)
        
        assert parsed["elements"] == ["重生", "系统", "逆袭"]
        assert parsed["quality"]["score"] == 3.3
```

### 步骤3：更新 skill 文档

**文件**：`.claude/skills/nm-material/SKILL.md`

已在之前更新，无需修改。

### 步骤4：更新执行方案文档

**文件**：`docs/classify_implementation.md`

补充说明：
- 取样策略（批次2）
- 信息扩展（批次3）
- 标签对接（批次1）

---

## 验证清单

### 功能验证

```bash
# 1. 标签对接验证
nm material classify start --limit 5
# 检查 genre_primary 是否在系统标签中

# 2. 取样验证
nm material classify status
# 检查 input tokens 应为 8000-10000（而非固定 4000）

# 3. 信息扩展验证
cat data/material_index.yaml | grep -E "elements|style|quality"
# 应有输出

# 4. 单元测试
pytest tests/test_classify.py -v
# 应全部通过
```

### 数据验证

```yaml
# 预期输出格式示例
materials:
  0001_凡人修仙传:
    genre_primary: 仙侠
    genre_secondary: 修真文明
    elements: [修仙, 升级, 凡人逆袭]
    style: {narrative: 朴素, tone: 冷峻, pace: 慢热}
    quality: {writing: 4, plot: 4, character: 4, score: 4.0}
    confidence: 0.95
```

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Token 消耗增加 | 成本增加 30-50% | 可配置采样章数，控制 max_chars |
| LLM 输出不稳定 | elements 不在系统标签中 | 校验时过滤 + 归一化 |
| 二级题材冲突 | genre_secondary 与 genre_primary 不匹配 | 使用 infer_primary_from_secondary 归一化 |
| 取样失败 | 章节检测失败 | 降级为全文前 8000 字 |

---

## 完成标准

1. ✅ genre 使用系统标签体系
2. ✅ 取样覆盖开头 + 中间 + 结尾
3. ✅ 输出包含 5+ 维度信息
4. ✅ 单元测试覆盖新增功能
5. ✅ CLI 命令正常工作
6. ✅ 文档更新完成