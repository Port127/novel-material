from pydantic import ValidationError
import pytest

from novel_material.worldbuilding.models import (
    WorldbuildingDimension,
    WorldbuildingEntity,
    WorldbuildingEvidence,
)


def test_worldbuilding_entity_defaults_are_stable() -> None:
    entity = WorldbuildingEntity(id="organization_x", type="organization", name="组织")

    assert entity.schema_version == "1.0.0"
    assert entity.aliases == ()
    assert entity.importance == "secondary"
    assert entity.evidence == ()


def test_worldbuilding_dimension_rejects_unknown_applicability() -> None:
    with pytest.raises(ValidationError):
        WorldbuildingDimension(
            id="x",
            name="未知维度",
            category="misc",
            applicability="maybe",
        )


def test_worldbuilding_evidence_defaults_to_fact_basis() -> None:
    evidence = WorldbuildingEvidence(chapter=3, summary="出现")

    assert evidence.basis == "fact"
