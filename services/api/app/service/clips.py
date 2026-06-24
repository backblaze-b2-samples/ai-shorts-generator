"""Sample-scoped Clips Library + shorts dashboard metrics.

Reads only this app's own prefixes (clips/, sources/, jobs/) — the per-app
scoped explorer that complements the full-bucket /files view.
"""

import re

from app.repo import (
    get_inline_presigned_url,
    get_json,
    get_presigned_url,
    list_keys,
)
from app.service.jobs import (
    CLIPS_PREFIX,
    JOBS_PREFIX,
    SOURCES_PREFIX,
    THUMBNAILS_PREFIX,
    _job_key,
)
from app.types import ClipItem, ClipsStats
from app.types.formatting import humanize_bytes

_DANGEROUS_KEY_RE = re.compile(r"(\.\./|/\.\.|\\|%2e%2e|%00|\x00)")
_JOB_ID_RE = re.compile(rf"^{re.escape(CLIPS_PREFIX)}([^/]+)/")


class ClipKeyError(Exception):
    def __init__(self, detail: str = "Invalid clip key"):
        self.detail = detail
        super().__init__(detail)


def _validate_clip_key(key: str) -> None:
    if not key or _DANGEROUS_KEY_RE.search(key.lower()):
        raise ClipKeyError()
    # Scope every clip op to this app's clips/ prefix — never the whole bucket.
    if not key.startswith(CLIPS_PREFIX):
        raise ClipKeyError("Key is outside the clips/ prefix")


def _job_id_for(key: str) -> str:
    m = _JOB_ID_RE.match(key)
    return m.group(1) if m else ""


def _thumbnail_url_for(key: str, available: set[str]) -> str | None:
    """Presigned poster URL for a clip, or None when no thumbnail exists.

    `clips/<job>/clip_N.mp4` -> `thumbnails/<job>/clip_N.jpg`. Only presign keys
    that actually exist (so the browser never gets a URL that 404s), and never
    let one bad key break the whole listing."""
    thumb_key = f"{THUMBNAILS_PREFIX}{key[len(CLIPS_PREFIX):-len('.mp4')]}.jpg"
    if thumb_key not in available:
        return None
    try:
        return get_inline_presigned_url(thumb_key)
    except RuntimeError:
        return None


def list_clips() -> list[ClipItem]:
    """List every rendered short under this app's clips/ prefix.

    Each clip is enriched with a first-frame poster URL (when one exists) and
    its source video's name/date, read once per job from jobs/<id>.json so the
    Clips page can group clips into per-video folders.
    """
    thumb_keys = {o["key"] for o in list_keys(THUMBNAILS_PREFIX)}
    job_cache: dict[str, dict | None] = {}

    items: list[ClipItem] = []
    for obj in list_keys(CLIPS_PREFIX):
        key = obj["key"]
        if not key.endswith(".mp4"):
            continue
        job_id = _job_id_for(key)
        if job_id not in job_cache:
            job_cache[job_id] = get_json(_job_key(job_id)) if job_id else None
        record = job_cache[job_id] or {}
        items.append(
            ClipItem(
                key=key,
                filename=key.rsplit("/", 1)[-1],
                job_id=job_id,
                size_bytes=obj["size"],
                size_human=humanize_bytes(obj["size"]),
                uploaded_at=obj["last_modified"],
                thumbnail_url=_thumbnail_url_for(key, thumb_keys),
                source_filename=record.get("source_filename"),
                job_created_at=record.get("created_at"),
            )
        )
    items.sort(key=lambda c: c.uploaded_at, reverse=True)
    return items


def get_clip_preview_url(key: str) -> str:
    """Inline (streamable) presigned URL for in-browser <video> playback."""
    _validate_clip_key(key)
    return get_inline_presigned_url(key)


def get_clip_download_url(key: str) -> str:
    """Attachment presigned URL for downloading the clip."""
    _validate_clip_key(key)
    return get_presigned_url(key, filename=key.rsplit("/", 1)[-1])


def get_shorts_stats() -> ClipsStats:
    """Dashboard metrics derived entirely from this app's own prefixes."""
    sources = list_keys(SOURCES_PREFIX)
    clips = [o for o in list_keys(CLIPS_PREFIX) if o["key"].endswith(".mp4")]
    thumbnails = list_keys(THUMBNAILS_PREFIX)
    storage = (
        sum(o["size"] for o in sources)
        + sum(o["size"] for o in clips)
        + sum(o["size"] for o in thumbnails)
    )

    # Total clip seconds comes from the durable job records (jobs/<id>.json),
    # the authoritative source — clip files carry no duration metadata.
    total_seconds = 0.0
    for obj in list_keys(JOBS_PREFIX):
        if not obj["key"].endswith(".json"):
            continue
        record = get_json(obj["key"]) or {}
        for clip in record.get("clips", []):
            total_seconds += float(clip.get("duration_seconds", 0) or 0)

    videos = len({o["key"] for o in sources})
    return ClipsStats(
        videos_processed=videos,
        clips_generated=len(clips),
        total_clip_seconds=round(total_seconds, 1),
        storage_bytes=storage,
        storage_human=humanize_bytes(storage),
    )
