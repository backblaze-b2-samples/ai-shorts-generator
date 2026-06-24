"""Job orchestration — the shorts pipeline, run as a FastAPI BackgroundTask.

B2 is the sole datastore: every job's status lives as jobs/<id>.json. The UI
polls GET /jobs/{id}. Steps: download source -> extract audio -> transcribe
(repo) -> detect moments (repo, Genblaze/OpenAI) -> render clips (render) ->
upload clips + captions, persisting status after each transition.
"""

import logging
import os
import tempfile
import uuid
from datetime import UTC, datetime

from app.config import settings
from app.repo import (
    detect_moments,
    download_file,
    get_json,
    put_json,
    transcribe_audio,
    upload_path,
)
from app.service import render
from app.types import ClipResult, JobRecord, Moment

logger = logging.getLogger(__name__)

# B2 prefixes owned by this app.
SOURCES_PREFIX = "sources/"
CLIPS_PREFIX = "clips/"
CAPTIONS_PREFIX = "captions/"
THUMBNAILS_PREFIX = "thumbnails/"
JOBS_PREFIX = "jobs/"
TRANSCRIPTS_PREFIX = "transcripts/"
MOMENTS_PREFIX = "moments/"


def _job_key(job_id: str) -> str:
    return f"{JOBS_PREFIX}{job_id}.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _save(job: JobRecord) -> None:
    job.updated_at = _now()
    put_json(_job_key(job.id), job.model_dump(mode="json"))


def get_job(job_id: str) -> JobRecord | None:
    data = get_json(_job_key(job_id))
    return JobRecord.model_validate(data) if data else None


def create_job(
    source_key: str,
    source_filename: str,
    clip_count: int | None = None,
    aspect: str | None = None,
) -> JobRecord:
    now = _now()
    job = JobRecord(
        id=uuid.uuid4().hex[:12],
        status="queued",
        source_key=source_key,
        source_filename=source_filename,
        clip_count=clip_count or settings.clips_per_video,
        aspect=aspect or settings.clip_aspect,
        created_at=now,
        updated_at=now,
        message="Queued for processing",
    )
    _save(job)
    return job


def _set(job: JobRecord, status, progress: int, message: str) -> None:
    job.status = status
    job.progress = progress
    job.message = message
    _save(job)
    logger.info("job %s -> %s (%d%%) %s", job.id, status, progress, message)


def run_job(job_id: str) -> None:
    """Execute the full pipeline. Safe to hand to BackgroundTasks.add_task."""
    job = get_job(job_id)
    if job is None:
        logger.error("run_job: job %s not found", job_id)
        return

    workdir = tempfile.mkdtemp(prefix=f"shorts-{job_id}-")
    try:
        src_path = os.path.join(workdir, job.source_filename or "source.mp4")
        _set(job, "transcribing", 10, "Downloading source from B2")
        download_file(job.source_key, src_path)

        wav_path = os.path.join(workdir, "audio.wav")
        render.extract_audio(src_path, wav_path)
        _set(job, "transcribing", 25, "Transcribing audio (Whisper)")
        segments = transcribe_audio(wav_path)
        put_json(f"{TRANSCRIPTS_PREFIX}{job_id}.json", {"segments": segments})
        if not segments:
            raise RuntimeError(
                "No speech detected in this video — there's nothing to turn into "
                "shorts. Check that it has a spoken audio track in the expected "
                "language (the default transcription model is base.en / English)."
            )

        _set(job, "detecting", 50, "Finding the best moments (AI)")
        raw_moments = _detect_moments_with_retry(segments, job, src_path)
        job.moments = [Moment(**m) for m in raw_moments]
        put_json(f"{MOMENTS_PREFIX}{job_id}.json", {"moments": raw_moments})
        _save(job)

        _set(job, "rendering", 65, f"Rendering {len(job.moments)} clips")
        job.clips = _render_and_upload(job, src_path, workdir)
        _save(job)

        _set(job, "complete", 100, f"Done — {len(job.clips)} clips ready")
    except Exception as exc:
        logger.exception("job %s failed", job_id)
        job.error = str(exc)
        _set(job, "failed", job.progress, f"Failed: {exc}")
    finally:
        _cleanup_dir(workdir)


def _detect_moments_with_retry(
    segments: list[dict], job: JobRecord, src_path: str
) -> list[dict]:
    """Pick moments, with one relaxed retry, and never return an empty list.

    The transcript has speech (the caller already guarded the empty case), so a
    zero-moment result means the model was too strict — we retry once with a
    looser brief. If even that yields nothing, raise so the job fails with an
    actionable reason instead of silently "completing" with no clips. Moments
    are bounded to the source duration (best-effort; None when ffprobe absent).
    """
    duration = render.probe_duration(src_path)
    moments = detect_moments(segments, job.clip_count, max_end=duration)
    if not moments:
        logger.warning(
            "job %s: strict pass found no moments; retrying with relaxed brief",
            job.id,
        )
        moments = detect_moments(
            segments, job.clip_count, relaxed=True, max_end=duration
        )
    if not moments:
        raise RuntimeError(
            "The AI found no clip-worthy moments in this video. Try a longer "
            "video, or one with clearer, more self-contained spoken segments."
        )
    return moments


def _render_and_upload(job: JobRecord, src_path: str, workdir: str) -> list[ClipResult]:
    clips: list[ClipResult] = []
    total = len(job.moments) or 1
    for i, moment in enumerate(job.moments):
        duration = moment.end - moment.start
        srt_path = None
        if moment.caption_lines:
            srt_path = os.path.join(workdir, f"clip_{i}.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(render.build_srt(moment.caption_lines, duration))

        out_path = os.path.join(workdir, f"clip_{i}.mp4")
        render.render_clip(
            src_path,
            render.ClipSpec(moment.start, moment.end, out_path, srt_path),
            job.aspect,
        )
        clip_key = f"{CLIPS_PREFIX}{job.id}/clip_{i}.mp4"
        upload_path(out_path, clip_key, "video/mp4")
        _make_thumbnail(job.id, i, out_path, workdir)
        if srt_path:
            cap_key = f"{CAPTIONS_PREFIX}{job.id}/clip_{i}.srt"
            upload_path(srt_path, cap_key, "text/plain")
        clips.append(
            ClipResult(
                key=clip_key,
                title=moment.title,
                duration_seconds=round(duration, 2),
                size_bytes=os.path.getsize(out_path),
            )
        )
        job.progress = 65 + int(30 * (i + 1) / total)
        _save(job)
    return clips


def _make_thumbnail(job_id: str, i: int, clip_path: str, workdir: str) -> None:
    """Extract + upload a first-frame poster for one clip. Non-fatal: a failure
    here is logged and swallowed so the clip (and the job) still ship."""
    try:
        thumb_path = os.path.join(workdir, f"clip_{i}.jpg")
        render.extract_thumbnail(clip_path, thumb_path)
        thumb_key = f"{THUMBNAILS_PREFIX}{job_id}/clip_{i}.jpg"
        upload_path(thumb_path, thumb_key, "image/jpeg")
    except Exception as exc:  # poster is best-effort — never fail the job over it
        logger.warning("thumbnail failed for clip %d of job %s: %s", i, job_id, exc)


def _cleanup_dir(path: str) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)
