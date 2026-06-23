"""Clips routes: the sample-scoped Clips Library + shorts dashboard stats."""

import logging

from fastapi import APIRouter, HTTPException

from app.service.clips import (
    ClipKeyError,
    get_clip_download_url,
    get_clip_preview_url,
    get_shorts_stats,
    list_clips,
)
from app.types import ClipItem, ClipsStats

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/clips", response_model=list[ClipItem])
async def list_clips_endpoint():
    return list_clips()


@router.get("/clips/stats", response_model=ClipsStats)
async def clips_stats_endpoint():
    return get_shorts_stats()


@router.get("/clips/{key:path}/preview")
async def clip_preview_endpoint(key: str):
    try:
        return {"url": get_clip_preview_url(key)}
    except ClipKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None


@router.get("/clips/{key:path}/download")
async def clip_download_endpoint(key: str):
    try:
        return {"url": get_clip_download_url(key)}
    except ClipKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
