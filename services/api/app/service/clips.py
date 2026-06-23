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
from app.service.jobs import CLIPS_PREFIX, JOBS_PREFIX, SOURCES_PREFIX
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


def list_clips() -> list[ClipItem]:
    """List every rendered short under this app's clips/ prefix."""
    items: list[ClipItem] = []
    for obj in list_keys(CLIPS_PREFIX):
        key = obj["key"]
        if not key.endswith(".mp4"):
            continue
        items.append(
            ClipItem(
                key=key,
                filename=key.rsplit("/", 1)[-1],
                job_id=_job_id_for(key),
                size_bytes=obj["size"],
                size_human=humanize_bytes(obj["size"]),
                uploaded_at=obj["last_modified"],
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
    storage = sum(o["size"] for o in sources) + sum(o["size"] for o in clips)

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
