from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import data_service as ds

router = APIRouter(tags=["tags"])


@router.get("/tags")
def get_tag_dict():
    return ds.get_tag_dict()


@router.get("/tags/usage")
def get_tag_usage():
    return ds.get_tag_usage()


class TagAddRequest(BaseModel):
    dimension: str
    value: str


class TagMergeRequest(BaseModel):
    dimension: str
    source: str
    target: str


@router.post("/tags/add")
def add_tag(req: TagAddRequest):
    result = ds.add_tag_value(req.dimension, req.value)
    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Failed"))
    return result


@router.post("/tags/merge")
def merge_tags(req: TagMergeRequest):
    result = ds.merge_tag_values(req.dimension, req.source, req.target)
    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Failed"))
    return result
