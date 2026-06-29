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

__all__ = [
    "LayeredWorldbuilding",
    "WorldbuildingDimension",
    "WorldbuildingEntity",
    "WorldbuildingEvidence",
    "WorldbuildingIndex",
    "WorldbuildingOverview",
    "WorldbuildingRelation",
    "WorldbuildingView",
    "load_worldbuilding_view",
]
