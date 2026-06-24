"""Scoped Clips Library tests — B2 list/get mocked, no network."""

import pytest

from app.service import clips
from app.service.clips import ClipKeyError


def _patch_listing(monkeypatch, objects, job_records=None):
    from datetime import UTC, datetime

    ts = datetime(2026, 6, 23, tzinfo=UTC)

    def fake_list_keys(prefix, max_keys=1000):
        return [
            {"key": k, "size": s, "last_modified": ts}
            for (k, s) in objects
            if k.startswith(prefix)
        ]

    records = job_records or {}
    monkeypatch.setattr(clips, "list_keys", fake_list_keys)
    monkeypatch.setattr(clips, "get_json", lambda key: records.get(key))
    # Presigning is a local op in production; stub it to a deterministic URL so
    # the test asserts on which clips got a poster, not on the signature.
    monkeypatch.setattr(
        clips, "get_inline_presigned_url", lambda key, **kw: f"https://signed/{key}"
    )


def test_list_clips_only_returns_mp4s_under_clips_prefix(monkeypatch):
    _patch_listing(
        monkeypatch,
        [
            ("clips/job1/clip_0.mp4", 100),
            ("clips/job1/clip_0.srt", 5),  # not an mp4 -> excluded
            ("sources/job1/video.mp4", 999),  # different prefix -> excluded
        ],
    )
    items = clips.list_clips()
    assert [c.key for c in items] == ["clips/job1/clip_0.mp4"]
    assert items[0].job_id == "job1"


def test_list_clips_includes_thumbnail_url_only_when_poster_exists(monkeypatch):
    _patch_listing(
        monkeypatch,
        [
            ("clips/job1/clip_0.mp4", 100),
            ("clips/job1/clip_1.mp4", 100),
            ("thumbnails/job1/clip_0.jpg", 5),  # only clip_0 has a poster
        ],
    )
    by_key = {c.key: c for c in clips.list_clips()}
    assert (
        by_key["clips/job1/clip_0.mp4"].thumbnail_url
        == "https://signed/thumbnails/job1/clip_0.jpg"
    )
    assert by_key["clips/job1/clip_1.mp4"].thumbnail_url is None


def test_list_clips_enriches_source_from_job_record(monkeypatch):
    from datetime import UTC, datetime

    created = datetime(2026, 6, 20, tzinfo=UTC)
    _patch_listing(
        monkeypatch,
        [("clips/job1/clip_0.mp4", 100)],
        job_records={
            "jobs/job1.json": {
                "source_filename": "vacation.mp4",
                "created_at": created.isoformat(),
                "clips": [],
            }
        },
    )
    item = clips.list_clips()[0]
    assert item.source_filename == "vacation.mp4"
    assert item.job_created_at == created


def test_list_clips_orphan_job_record_degrades_gracefully(monkeypatch):
    # No job record for job1 (get_json -> None): enrichment is null, but the
    # poster still resolves from the listing and nothing crashes.
    _patch_listing(
        monkeypatch,
        [
            ("clips/job1/clip_0.mp4", 100),
            ("thumbnails/job1/clip_0.jpg", 5),
        ],
    )
    item = clips.list_clips()[0]
    assert item.source_filename is None
    assert item.job_created_at is None
    assert item.thumbnail_url == "https://signed/thumbnails/job1/clip_0.jpg"


def test_clip_preview_rejects_out_of_scope_key():
    with pytest.raises(ClipKeyError):
        clips.get_clip_preview_url("sources/secret/video.mp4")


def test_clip_preview_rejects_traversal():
    with pytest.raises(ClipKeyError):
        clips.get_clip_preview_url("clips/../../etc/passwd")


def test_shorts_stats_counts_sources_and_clips(monkeypatch):
    _patch_listing(
        monkeypatch,
        [
            ("sources/a/v.mp4", 1000),
            ("clips/a/clip_0.mp4", 200),
            ("clips/a/clip_1.mp4", 300),
            ("thumbnails/a/clip_0.jpg", 10),
            ("thumbnails/a/clip_1.jpg", 10),
        ],
    )
    stats = clips.get_shorts_stats()
    assert stats.videos_processed == 1
    assert stats.clips_generated == 2
    # Storage includes sources + clips + posters.
    assert stats.storage_bytes == 1520
