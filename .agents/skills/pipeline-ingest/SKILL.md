# pipeline-ingest

入库 + 格式清洗 + 章节切分。这是 Pipeline 的第一个阶段，不涉及任何 LLM 调用。

## 当前状态

> ⚠️ `pipeline.py` 目前**没有**独立的 `ingest` 子命令（缺陷 C9）。
> 需要直接调用底层脚本。

## 执行命令

```bash
python scripts/core/ingest.py <小说文件路径>
```

## 前置条件

- 输入文件为 UTF-8 编码的 `.txt` 文件
- 章节标题必须使用阿拉伯数字格式（如"第1章"、"第1回"）
- ⚠️ 中文数字格式（如"第一章"）当前**不支持**（缺陷 C1）。根因是缺少预处理层，待 `preprocess.py` 模块完成后此限制将消除

## 处理流程

1. 读取原文文件
2. 用正则表达式检测章节标题行号
3. 按章节行号切分内容
4. 保存 `source.txt`（清洗后原文，仅保留章节内容）
5. 生成 `chapter_index.yaml`（章号 / 标题 / 起止行号 / 字数）
6. 生成 `meta.yaml`（name 取自文件名，author 为 TBD，status 为 clean）
7. 创建空目录结构（`outline/` `characters/profiles/` `worldbuilding/`）
8. 初始化空的 `chapters.yaml`
9. 更新 `data/index.yaml` 全局索引

## 产物

```
data/novels/{material_id}/
├── meta.yaml               # status: clean
├── source.txt              # 清洗后原文
├── chapter_index.yaml      # 章节索引
├── chapters.yaml           # 空列表（待章级分析填充）
├── outline/                # 空目录
├── characters/profiles/    # 空目录
└── worldbuilding/          # 空目录
```

## 成功校验

1. 终端输出 `识别到 N 个章节`，N > 0
2. `chapter_index.yaml` 存在且列表非空
3. `meta.yaml` 中 `status: clean`

## 已知问题

- 第 123 行 `material_dir` 变量未定义，会导致 `NameError`（缺陷 C2）
- 如果原文中没有任何匹配的章节标题，函数返回 `None` 且不创建任何文件
