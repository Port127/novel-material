# 检索容量与候选质量门禁

## 当前状态

容量实验框架和质量门禁已经固化，但 **25 万、50 万、250 万章实测尚未执行**。原因是 Golden Query 人工相关性标注已按当前决策延期；缺少可信基线时运行百万级候选实验只能得到速度数字，无法判断质量是否下降。

生产检索继续保留完整 `vector(4096)` 精确排序，不建立 ANN 索引，不修改生产 schema。

## 安全实验计划

以下命令只输出机器信息、预计磁盘空间、隔离 schema 名称和必需指标，不连接数据库：

```bash
python scripts/benchmark_search.py --rows 250000 --queries eval/search_queries.yaml --mode exact
python scripts/benchmark_search.py --rows 500000 --queries eval/search_queries.yaml --mode exact
python scripts/benchmark_search.py --rows 2500000 --queries eval/search_queries.yaml --mode exact --confirm-large
```

真实实验执行器必须满足：

- 只写独立的 `search_benchmark` schema，不写生产表；
- 运行前输出预计磁盘占用；
- 250 万行必须再次显式确认；
- 记录 P50/P95、峰值内存、数据库 buffers、吞吐、逐查询结果和硬件信息；
- 候选实验至少召回 1000 条，再使用原始 4096 维向量精确重排。

## 生产候选门禁

只有同时满足以下条件，才能另开生产 ANN 设计：

- Candidate Recall ≥ 0.98；
- 最终 nDCG@10 相比精确基线下降不超过 0.01；
- 质量模式 P95 ≤ 180 秒；
- 没有 Golden Query 从“合格”退化为“无相关结果”。

门禁由 `candidate_gate()` 固定实现。当前没有实测结论，因此不得声称近似候选优于或等同于精确检索。
