"""搜索服务、CLI、评测与 Agent 共用的稳定数据契约。"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

DocumentType = Literal[
    "chapter",
    "event",
    "outline",
    "character",
    "world",
    "detail",
    "insight",
]
SearchMode = Literal["quality", "exact"]


class SourceLocation(BaseModel):
    """检索结果在原始素材中的位置。"""

    chapter: int | None = None
    start_line: int | None = None
    end_line: int | None = None


class NeighborContext(BaseModel):
    """章节结果的相邻章节摘要。"""

    previous_summary: str | None = None
    next_summary: str | None = None


class SearchRequest(BaseModel):
    """统一检索请求。"""

    query: str = Field(min_length=1)
    document_types: list[DocumentType] = Field(default_factory=lambda: ["chapter"])
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=100)
    candidate_limit: int = Field(default=200, ge=1, le=1000)
    mode: SearchMode = "quality"
    time_budget_seconds: int = Field(default=180, ge=1, le=180)

    @model_validator(mode="after")
    def validate_candidate_limit(self):
        """确保候选池能够覆盖最终结果数量。"""
        if self.candidate_limit < self.limit:
            raise ValueError("candidate_limit 不能小于 limit")
        return self


class SearchResult(BaseModel):
    """跨检索类型复用的单条结果。"""

    result_id: str
    document_type: DocumentType
    material_id: str
    entity_id: str | None = None
    chapter: int | None = None
    title: str = ""
    summary: str = ""
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: SourceLocation | None = None
    neighbors: NeighborContext | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    matched_fields: list[str] = Field(default_factory=list)
    final_score: float | None = None
    rank_reason: str = ""


class SearchTrace(BaseModel):
    """一次检索的阶段、耗时与降级信息。"""

    stages: list[str] = Field(default_factory=list)
    candidate_counts: dict[str, int] = Field(default_factory=dict)
    elapsed_ms: dict[str, float] = Field(default_factory=dict)
    embedding_version: str | None = None
    degraded: bool = False
    degradation_reasons: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """面向 CLI、评测与外部 Agent 的统一响应。"""

    query: str
    results: list[SearchResult] = Field(default_factory=list)
    trace: SearchTrace
