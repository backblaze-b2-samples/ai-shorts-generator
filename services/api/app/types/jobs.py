from datetime import datetime
from typing import Literal

from pydantic import BaseModel

JobStatus = Literal[
    "queued",
    "transcribing",
    "detecting",
    "rendering",
    "complete",
    "failed",
]


class Moment(BaseModel):
    start: float
    end: float
    title: str
    hook: str = ""
    caption_lines: list[str] = []


class ClipResult(BaseModel):
    key: str
    title: str
    duration_seconds: float
    size_bytes: int


class JobRecord(BaseModel):
    """Persisted as jobs/<id>.json in B2 — B2 is the sole datastore."""

    id: str
    status: JobStatus
    source_key: str
    source_filename: str
    clip_count: int
    aspect: str
    created_at: datetime
    updated_at: datetime
    progress: int = 0  # 0-100
    message: str = ""
    moments: list[Moment] = []
    clips: list[ClipResult] = []
    error: str | None = None


class JobCreateResponse(BaseModel):
    id: str
    status: JobStatus
