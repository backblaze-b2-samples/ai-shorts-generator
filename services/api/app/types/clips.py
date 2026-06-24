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
    # Enrichment for the Clips page (all optional so old data degrades cleanly):
    # a presigned first-frame poster URL, and the source video's name/date so
    # clips can be grouped into per-video folders.
    thumbnail_url: str | None = None
    source_filename: str | None = None
    job_created_at: datetime | None = None


class ClipsStats(BaseModel):
    """Shorts-specific dashboard metrics derived from this app's prefixes."""

    videos_processed: int
    clips_generated: int
    total_clip_seconds: float
    storage_bytes: int
    storage_human: str
