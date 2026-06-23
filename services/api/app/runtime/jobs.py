"""Job routes: start a shorts job (upload source + enqueue) and poll status."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request, UploadFile

from app.config import settings
from app.repo import upload_file
from app.service.jobs import SOURCES_PREFIX, create_job, get_job, run_job
from app.service.upload import sanitize_filename
from app.types import JobCreateResponse, JobRecord

logger = logging.getLogger(__name__)

router = APIRouter()

# Long videos are larger than the generic upload cap — allow up to 1 GiB here.
MAX_SOURCE_BYTES = 1024 * 1024 * 1024
ALLOWED_SOURCE_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska"}


@router.post("/jobs", response_model=JobCreateResponse)
async def start_job(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile,
    clip_count: int = Form(default=0),
    aspect: str = Form(default=""),
):
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported source type '{content_type}'. Upload a video.",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_SOURCE_BYTES:
            raise HTTPException(status_code=413, detail="Source video too large")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    safe_name = sanitize_filename(file.filename or "source.mp4")
    # Each job gets its own sources/<uuid>/ prefix so deletes stay scoped.
    source_key = f"{SOURCES_PREFIX}{uuid.uuid4().hex[:12]}/{safe_name}"
    upload_file(data, source_key, content_type)

    job = create_job(
        source_key=source_key,
        source_filename=safe_name,
        clip_count=clip_count or settings.clips_per_video,
        aspect=aspect or settings.clip_aspect,
    )
    background.add_task(run_job, job.id)
    logger.info("job %s started for source=%s", job.id, source_key)
    return JobCreateResponse(id=job.id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobRecord)
async def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
