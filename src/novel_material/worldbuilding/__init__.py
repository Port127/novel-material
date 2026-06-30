"""世界观分层契约与兼容读取入口。"""

from .models import (
    LayeredWorldbuilding,
    WorldbuildingDimension,
    WorldbuildingEntity,
    WorldbuildingEvidence,
    WorldbuildingIndex,
    WorldbuildingOverview,
    WorldbuildingRelation,
    WorldbuildingView,
)
from .reader import load_worldbuilding_view
from .dimensions import DimensionRoutingResult, resolve_worldbuilding_dimensions
from .normalizer import normalize_layered_worldbuilding_response, slugify_entity_id

__all__ = [
    "DimensionRoutingResult",
    "LayeredWorldbuilding",
    "WorldbuildingDimension",
    "WorldbuildingEntity",
    "WorldbuildingEvidence",
    "WorldbuildingIndex",
    "WorldbuildingOverview",
    "WorldbuildingRelation",
    "WorldbuildingView",
    "load_worldbuilding_view",
    "normalize_layered_worldbuilding_response",
    "resolve_worldbuilding_dimensions",
    "slugify_entity_id",
]
