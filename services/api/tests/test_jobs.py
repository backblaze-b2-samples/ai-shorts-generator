"""Job lifecycle tests — all B2 + ffmpeg + AI calls mocked, no network."""

from app.service import jobs
from app.types import JobRecord


class _FakeB2:
    """In-memory stand-in for B2 JSON storage (jobs/<id>.json etc.)."""

    def __init__(self):
        self.store: dict[str, dict] = {}

    def put_json(self, key, payload):
        self.store[key] = payload

    def get_json(self, key):
        return self.store.get(key)


def _patch_b2(monkeypatch):
    fake = _FakeB2()
    monkeypatch.setattr(jobs, "put_json", fake.put_json)
    monkeypatch.setattr(jobs, "get_json", fake.get_json)
    return fake


def test_create_job_persists_queued_record(monkeypatch):
    fake = _patch_b2(monkeypatch)
    job = jobs.create_job("sources/abc/video.mp4", "video.mp4", clip_count=2, aspect="9:16")
    assert job.status == "queued"
    assert job.clip_count == 2
    # Persisted to jobs/<id>.json in B2 — B2 is the sole datastore.
    assert f"jobs/{job.id}.json" in fake.store
    reloaded = jobs.get_job(job.id)
    assert reloaded is not None
    assert reloaded.source_key == "sources/abc/video.mp4"


def test_run_job_happy_path(monkeypatch):
    _patch_b2(monkeypatch)
    job = jobs.create_job("sources/abc/v.mp4", "v.mp4", clip_count=1, aspect="9:16")

    monkeypatch.setattr(jobs, "download_file", lambda key, dest: None)
    monkeypatch.setattr(jobs.render, "extract_audio", lambda src, wav: None)
    monkeypatch.setattr(
        jobs, "transcribe_audio", lambda path: [{"start": 0, "end": 30, "text": "hi"}]
    )
    monkeypatch.setattr(
        jobs,
        "detect_moments",
        lambda segs, n: [
            {"start": 1.0, "end": 21.0, "title": "Clip", "hook": "", "caption_lines": ["x"]}
        ],
    )
    # render_clip is the only step that would touch ffmpeg/disk — stub it to
    # create the expected output file so the real os.path.getsize works.
    def _fake_render_clip(src, spec, aspect):
        with open(spec.out_path, "wb") as f:
            f.write(b"fake-mp4-bytes")

    monkeypatch.setattr(jobs.render, "render_clip", _fake_render_clip)
    monkeypatch.setattr(jobs, "upload_path", lambda local, key, ct: None)

    jobs.run_job(job.id)

    done = jobs.get_job(job.id)
    assert done.status == "complete"
    assert done.progress == 100
    assert len(done.clips) == 1
    assert done.clips[0].key == f"clips/{job.id}/clip_0.mp4"
    assert done.error is None


def test_run_job_records_failure(monkeypatch):
    _patch_b2(monkeypatch)
    job = jobs.create_job("sources/abc/v.mp4", "v.mp4")

    def _boom(key, dest):
        raise RuntimeError("B2 download failed")

    monkeypatch.setattr(jobs, "download_file", _boom)
    jobs.run_job(job.id)

    failed = jobs.get_job(job.id)
    assert failed.status == "failed"
    assert "B2 download failed" in (failed.error or "")


def test_get_job_missing_returns_none(monkeypatch):
    _patch_b2(monkeypatch)
    assert jobs.get_job("does-not-exist") is None


def test_job_record_roundtrips_through_json():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    rec = JobRecord(
        id="abc", status="complete", source_key="sources/x/v.mp4",
        source_filename="v.mp4", clip_count=1, aspect="9:16",
        created_at=now, updated_at=now,
    )
    dumped = rec.model_dump(mode="json")
    assert JobRecord.model_validate(dumped).id == "abc"
