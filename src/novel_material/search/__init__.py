"""素材检索模块。"""

from .outline import search_outlines
from .character import search_characters
from .world import search_worldbuilding
from .detail import search_detail
from .chapter import search_chapters
from .event import search_events
from .models import (
    DocumentType,
    NeighborContext,
    SearchMode,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SearchTrace,
    SourceLocation,
)
from .service import SearchService, SearchServiceError

__all__ = [
    "search_outlines",
    "search_characters",
    "search_worldbuilding",
    "search_detail",
    "search_chapters",
    "search_events",
    "DocumentType",
    "NeighborContext",
    "SearchMode",
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "SearchTrace",
    "SourceLocation",
    "SearchService",
    "SearchServiceError",
]
