from datetime import datetime

from pydantic import BaseModel


class ClipItem(BaseModel):
    """A rendered short in this app's scoped Clips Library."""

    key: str
    filename: str
    job_id: str
    size_bytes: int
    size_human: str
    uploaded_at: datetime


class ClipsStats(BaseModel):
    """Shorts-specific dashboard metrics derived from this app's prefixes."""

    videos_processed: int
    clips_generated: int
    total_clip_seconds: float
    storage_bytes: int
    storage_human: str
