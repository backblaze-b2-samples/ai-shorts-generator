"""Scoped Clips Library tests — B2 list/get mocked, no network."""

import pytest

from app.service import clips
from app.service.clips import ClipKeyError


def _patch_listing(monkeypatch, objects):
    from datetime import UTC, datetime

    ts = datetime(2026, 6, 23, tzinfo=UTC)

    def fake_list_keys(prefix, max_keys=1000):
        return [
            {"key": k, "size": s, "last_modified": ts}
            for (k, s) in objects
            if k.startswith(prefix)
        ]

    monkeypatch.setattr(clips, "list_keys", fake_list_keys)
    monkeypatch.setattr(clips, "get_json", lambda key: {"clips": []})


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
        ],
    )
    stats = clips.get_shorts_stats()
    assert stats.videos_processed == 1
    assert stats.clips_generated == 2
    assert stats.storage_bytes == 1500
