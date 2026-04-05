# Deterministic Graders

确定性验证规则。

## YAML 格式验证

### index.yaml

```python
def validate_index_yaml(content):
    # 必须包含 materials 字段
    assert "materials" in content
    # 每个 material 必须包含必要字段
    for m in content["materials"]:
        assert all(k in m for k in ["id", "type", "name", "folder", "status", "added"])
        # ID 格式验证
        assert re.match(r"nm_(novel|image|reference)_\d{8}_[a-z0-9]{4}", m["id"])
```

### plot_index.yaml

```python
def validate_plot_index_yaml(content):
    # 自动汇总，验证结构存在
    assert "plots" in content or len(content) > 0
```

### character_index.yaml

```python
def validate_character_index_yaml(content):
    # 自动汇总，验证结构存在
    assert "characters" in content or len(content) > 0
```

### tags.yaml

```python
def validate_tags_yaml(content):
    # 必须定义 6 层标签
    required_layers = ["content", "character", "emotion", "structure", "technique", "physical"]
    for layer in required_layers:
        assert layer in content
```

### scene.yaml

```python
def validate_scene_yaml(content):
    # 必须包含基础字段
    assert all(k in content for k in ["scene_id", "chapter", "title", "content", "tags"])
    # 标签必须覆盖 6 层
    tags = content["tags"]
    required_dims = ["scene_type", "emotion", "plot_stage", "setting"]
    for dim in required_dims:
        assert dim in tags
```

## 链接可解析验证

```python
def validate_links(docs_path):
    # 验证 AGENTS.md 中的链接
    # 验证 ARCHITECTURE.md 中的链接
    # 验证 docs/*.md 中的链接
    for link in extract_links(docs_path):
        assert os.path.exists(link.target)
```

## ID 唯一性验证

```python
def validate_id_uniqueness(index_yaml):
    ids = [m["id"] for m in index_yaml["materials"]]
    assert len(ids) == len(set(ids))  # 无重复
```

## 文件存在验证

```python
def validate_file_paths(index_yaml, base_path):
    for m in index_yaml["materials"]:
        folder = m.get("folder")
        assert os.path.exists(os.path.join(base_path, folder))
```

## 相关文档

- [../index.md](../index.md)
- [rubrics.md](rubrics.md)