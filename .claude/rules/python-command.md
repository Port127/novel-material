# Python 命令规范

项目使用 conda 环境 `env3.12`，所有 Python 脚本调用必须使用 `python`，禁止使用 `python3`。

```bash
# 正确
python scripts/...

# 错误
python3 scripts/...
```

**原因**：`python` 指向 conda 环境的正确 Python 3.12.12，`python3` 可能调用错误的系统 Python。