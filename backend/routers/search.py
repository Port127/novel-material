from fastapi import APIRouter, Query
from typing import Optional

from services import data_service as ds

router = APIRouter(tags=["search"])


@router.get("/search/events")
def search_events(
    event_type: Optional[str] = None,
    conflict: Optional[str] = None,
    stakes: Optional[str] = None,
    relationship: Optional[str] = None,
    interaction: Optional[str] = None,
    character_moment: Optional[str] = None,
    emotion: Optional[str] = None,
    reader_effect: Optional[str] = None,
    plot_function: Optional[str] = None,
    plot_stage: Optional[str] = None,
    technique: Optional[str] = None,
    dialogue_type: Optional[str] = None,
    info_delivery: Optional[str] = None,
    setting: Optional[str] = None,
    time_weather: Optional[str] = None,
    pacing: Optional[str] = None,
    pov: Optional[str] = None,
    power_dynamic: Optional[str] = None,
    moral_spectrum: Optional[str] = None,
    scale: Optional[str] = None,
    character: Optional[str] = None,
    material: Optional[str] = None,
    tension_min: Optional[int] = None,
    tension_max: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
):
    filters = dict(
        event_type=event_type, conflict=conflict, stakes=stakes,
        relationship=relationship, interaction=interaction,
        character_moment=character_moment, emotion=emotion,
        reader_effect=reader_effect, plot_function=plot_function,
        plot_stage=plot_stage, technique=technique,
        dialogue_type=dialogue_type, info_delivery=info_delivery,
        setting=setting, time_weather=time_weather,
        pacing=pacing, pov=pov, power_dynamic=power_dynamic,
        moral_spectrum=moral_spectrum, scale=scale,
        character=character, material=material,
        tension_min=tension_min, tension_max=tension_max,
        limit=limit,
    )
    return ds.search_events(filters)


@router.get("/search/characters")
def search_characters(
    name: Optional[str] = None,
    archetype: Optional[str] = None,
    role: Optional[str] = None,
    material: Optional[str] = None,
    moral_spectrum: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    return ds.search_characters(dict(
        name=name, archetype=archetype, role=role,
        material=material, moral_spectrum=moral_spectrum,
        limit=limit,
    ))


@router.get("/search/text")
def search_text(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    return ds.search_text(query, limit)


@router.get("/stats")
def get_stats():
    return ds.get_dashboard_stats()
