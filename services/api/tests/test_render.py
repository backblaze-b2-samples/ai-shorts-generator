"""ffmpeg arg-builder + SRT tests. No ffmpeg subprocess is ever spawned —
the builders are pure functions and the run path is mocked."""

from app.service import render
from app.service.render import ClipSpec


def test_clip_args_center_crop_to_9_16():
    spec = ClipSpec(start=12.0, end=42.0, out_path="/tmp/clip.mp4")
    args = render.build_clip_args("/tmp/src.mp4", spec, "9:16")
    joined = " ".join(args)
    # Seek before input, correct duration (end-start), libx264 + faststart.
    assert "-ss 12.00" in joined
    assert "-t 30.00" in joined
    assert "libx264" in joined
    assert "+faststart" in joined
    # Center crop to the 9:16 column then scale to 1080x1920.
    assert "crop=ih*1080/1920:ih" in joined
    assert "scale=1080:1920" in joined


def test_clip_args_burn_captions_when_srt_present():
    spec = ClipSpec(start=0.0, end=20.0, out_path="/tmp/c.mp4", srt_path="/tmp/c.srt")
    args = render.build_clip_args("/tmp/src.mp4", spec, "9:16")
    joined = " ".join(args)
    assert "subtitles=" in joined


def test_clip_args_no_subtitles_filter_without_srt():
    spec = ClipSpec(start=0.0, end=20.0, out_path="/tmp/c.mp4")
    args = render.build_clip_args("/tmp/src.mp4", spec, "9:16")
    assert "subtitles=" not in " ".join(args)


def test_extract_audio_args_mono_16k_wav():
    args = render.build_extract_audio_args("/tmp/src.mp4", "/tmp/a.wav")
    joined = " ".join(args)
    assert "-ac 1" in joined
    assert "-ar 16000" in joined
    assert joined.endswith("/tmp/a.wav")


def test_build_srt_spreads_cues_across_duration():
    srt = render.build_srt(["one", "two"], duration=10.0)
    assert "00:00:00,000 --> 00:00:05,000" in srt
    assert "00:00:05,000 --> 00:00:10,000" in srt
    assert "one" in srt and "two" in srt


def test_build_srt_empty_when_no_lines():
    assert render.build_srt([], duration=10.0) == ""


def test_unknown_aspect_falls_back_to_9_16():
    spec = ClipSpec(start=0.0, end=5.0, out_path="/tmp/c.mp4")
    args = render.build_clip_args("/tmp/src.mp4", spec, "bogus")
    assert "scale=1080:1920" in " ".join(args)


def test_ffmpeg_bin_resolves_to_a_path(monkeypatch):
    # With no system ffmpeg, it must fall back to the bundled binary.
    monkeypatch.setattr(render.shutil, "which", lambda _name: None)
    render._supports_filter.cache_clear()
    assert render.ffmpeg_bin()  # non-empty path string


def test_ffmpeg_bin_uses_system_when_subtitles_supported(monkeypatch):
    # A system ffmpeg that supports `subtitles` (libass) is preferred as-is.
    monkeypatch.setattr(render.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(render, "_supports_filter", lambda _bin, _name: True)
    assert render.ffmpeg_bin() == "/usr/bin/ffmpeg"


def test_ffmpeg_bin_falls_back_when_subtitles_unsupported(monkeypatch):
    # A slim system ffmpeg (no libass/subtitles) must NOT be chosen; we fall
    # back to the bundled imageio-ffmpeg binary so captions still render.
    monkeypatch.setattr(render.shutil, "which", lambda _name: "/opt/homebrew/bin/ffmpeg")
    monkeypatch.setattr(render, "_supports_filter", lambda _bin, _name: False)
    monkeypatch.setattr(render, "_bundled_ffmpeg", lambda: "/bundled/ffmpeg")
    assert render.ffmpeg_bin() == "/bundled/ffmpeg"


def test_supports_filter_parses_filters_output(monkeypatch):
    # Parse a representative `ffmpeg -filters` table without spawning ffmpeg.
    class _Proc:
        returncode = 0
        stdout = (
            "Filters:\n"
            " T.C drawtext          V->V       Draw text ...\n"
            " ... subtitles         V->V       Render text subtitles ...\n"
            " ... scale             V->V       Scale the input video ...\n"
        )

    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: _Proc())
    render._supports_filter.cache_clear()
    assert render._supports_filter("/any/ffmpeg", "subtitles") is True
    assert render._supports_filter("/any/ffmpeg", "nope") is False


def test_supports_filter_false_on_probe_failure(monkeypatch):
    # If the binary can't be run, treat the filter as unsupported (no crash).
    def _boom(*_a, **_k):
        raise OSError("not executable")

    monkeypatch.setattr(render.subprocess, "run", _boom)
    render._supports_filter.cache_clear()
    assert render._supports_filter("/missing/ffmpeg", "subtitles") is False


def test_run_raises_on_nonzero_exit(monkeypatch):
    class _Proc:
        returncode = 1
        stderr = "boom\nffmpeg error tail"

    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: _Proc())
    try:
        render._run(["ffmpeg", "-y"])
    except RuntimeError as e:
        assert "ffmpeg failed" in str(e)
    else:
        raise AssertionError("expected RuntimeError on ffmpeg failure")
