from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from services import data_service as ds

router = APIRouter(tags=["materials"])


@router.get("/materials")
def list_materials():
    return ds.list_materials()


@router.get("/materials/{material_id}")
def get_material(material_id: str):
    result = ds.get_material(material_id)
    if not result:
        raise HTTPException(404, "Material not found")
    return result


@router.get("/materials/{material_id}/outline")
def get_outline(material_id: str):
    result = ds.get_outline(material_id)
    if not result:
        raise HTTPException(404, "Outline not found")
    return result


@router.get("/materials/{material_id}/worldbuilding")
def get_worldbuilding(material_id: str):
    result = ds.get_worldbuilding(material_id)
    if not result:
        raise HTTPException(404, "Worldbuilding not found")
    return result


@router.get("/materials/{material_id}/characters")
def get_characters(material_id: str):
    result = ds.get_characters_yaml(material_id)
    if not result:
        raise HTTPException(404, "Characters not found")
    return result


@router.get("/materials/{material_id}/tags")
def get_tags(material_id: str):
    result = ds.get_novel_tags(material_id)
    if not result:
        raise HTTPException(404, "Tags not found")
    return result


@router.get("/materials/{material_id}/scenes")
def get_scenes(
    material_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    return ds.get_scenes(material_id, page, limit)


@router.get("/materials/{material_id}/scenes/{scene_id}")
def get_scene(material_id: str, scene_id: str):
    result = ds.get_scene_detail(material_id, scene_id)
    if not result:
        raise HTTPException(404, "Scene not found")
    return result


@router.get("/materials/{material_id}/stats")
def get_stats(material_id: str):
    result = ds.get_stats(material_id)
    if not result:
        raise HTTPException(404, "Stats not found")
    return result


@router.get("/materials/{material_id}/stats/html")
def get_stats_html(material_id: str):
    result = ds.get_stats_html(material_id)
    if not result:
        raise HTTPException(404, "Stats HTML not found")
    return HTMLResponse(content=result)
