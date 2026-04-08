import os
import json
import uuid
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from services import data_service as ds
from services import pipeline_service as ps

router = APIRouter(tags=["pipeline"])

UPLOAD_DIR = ds.DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload")
async def upload_novel(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
):
    if not file.filename:
        raise HTTPException(400, "Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".txt", ".epub", ".md"):
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    today = datetime.now().strftime("%Y%m%d")
    rand4 = uuid.uuid4().hex[:4]
    material_id = f"nm_novel_{today}_{rand4}"

    novel_dir = ds.NOVELS_DIR / material_id
    novel_dir.mkdir(parents=True, exist_ok=True)

    source_file = novel_dir / f"source{suffix}"
    content = await file.read()
    source_file.write_bytes(content)

    novel_name = name or Path(file.filename).stem
    meta = {
        "material_id": material_id,
        "name": novel_name,
        "author": author or "未知",
        "source_file": str(source_file.relative_to(ds.PROJECT_ROOT)),
        "status": "raw",
        "added": datetime.now().isoformat(),
    }
    ds._write_yaml(novel_dir / "meta.yaml", meta)
    ds.register_material(material_id, novel_name, author or "未知")

    return {
        "material_id": material_id,
        "name": novel_name,
        "message": "上传成功，可以开始 pipeline",
    }


@router.get("/pipeline/{material_id}/status")
def get_pipeline_status(material_id: str):
    status = ps.get_status(material_id)
    return status


@router.post("/pipeline/{material_id}/trigger")
async def trigger_pipeline(
    material_id: str,
    background_tasks: BackgroundTasks,
    stage: str = "ingest",
):
    valid_stages = ("ingest", "format", "build-index", "analyze", "scenes", "finalize")
    if stage not in valid_stages:
        raise HTTPException(400, f"Invalid stage: {stage}. Valid: {valid_stages}")

    nd = ds._novel_dir(material_id)
    if not nd.exists():
        raise HTTPException(404, "Material not found")

    current = ps.get_status(material_id)
    if current.get("running"):
        raise HTTPException(409, "Pipeline already running for this material")

    needs_llm = stage in ("analyze", "scenes", "finalize")
    if needs_llm:
        llm_cfg = ps.get_llm_config()
        if not llm_cfg.get("base_url") or not llm_cfg.get("api_key"):
            raise HTTPException(
                400, "LLM 未配置。请先在设置页面配置 LLM API 地址和密钥。"
            )

    background_tasks.add_task(ps.run_stage, material_id, stage)
    return {"message": f"已触发 {stage}", "material_id": material_id, "stage": stage}


@router.post("/pipeline/{material_id}/reset")
def reset_pipeline(material_id: str):
    nd = ds._novel_dir(material_id)
    if not nd.exists():
        raise HTTPException(404, "Material not found")
    status = ps.reset_status(material_id)
    return {"message": "已重置", "status": status}


@router.get("/settings/llm")
def get_llm_settings():
    cfg = ps.get_llm_config()
    safe = {k: v for k, v in cfg.items() if k != "api_key"}
    if cfg.get("api_key"):
        safe["api_key_set"] = True
    return safe


@router.put("/settings/llm")
async def save_llm_settings(body: dict):
    ps.save_llm_config(body)
    return {"message": "已保存"}


@router.post("/llm/test")
async def llm_test(body: dict = None):
    cfg = ps.get_llm_config()
    base = (body or {}).get("base_url") or cfg.get("base_url", "")
    key = (body or {}).get("api_key") or cfg.get("api_key", "")
    if not base or not key:
        raise HTTPException(400, "LLM not configured")

    import httpx
    url = base.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code < 400:
                return {"ok": True, "status": resp.status_code}
            url2 = base.rstrip("/") + "/chat/completions"
            resp2 = await client.post(url2, headers={**headers, "Content-Type": "application/json"},
                json={"model": (body or {}).get("model") or cfg.get("model", ""), "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1})
            return {"ok": resp2.status_code < 400, "status": resp2.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/llm/proxy")
async def llm_proxy(body: dict):
    cfg = ps.get_llm_config()
    if not cfg.get("base_url") or not cfg.get("api_key"):
        raise HTTPException(400, "LLM not configured")

    import httpx

    base = cfg["base_url"].rstrip("/")
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": body.get("model") or cfg.get("model", "gpt-4"),
        "messages": body.get("messages", []),
        "temperature": body.get("temperature", 0.7),
    }
    if body.get("max_tokens"):
        payload["max_tokens"] = body["max_tokens"]

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text)
        return resp.json()
