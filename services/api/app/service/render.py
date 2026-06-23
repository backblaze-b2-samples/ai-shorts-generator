"""ffmpeg rendering — pure local processing (no SDK, no boto3).

Lives in the service layer because it orchestrates a local tool over files
that repo/ has already fetched from / will persist to B2. Prefers a system
`ffmpeg`/`ffprobe`; falls back to the bundled `imageio-ffmpeg` binary so the
demo runs with no system install.

The arg-builder functions are split out from the subprocess calls so they can
be unit-tested without spawning ffmpeg (see tests/test_render.py).
"""

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Aspect ratio -> output WxH. 9:16 vertical is the default for shorts.
_ASPECT_DIMENSIONS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}


def ffmpeg_bin() -> str:
    """System ffmpeg if present, else the bundled imageio-ffmpeg binary."""
    system = shutil.which("ffmpeg")
    if system:
        return system
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def ffprobe_bin() -> str | None:
    """System ffprobe if present. imageio-ffmpeg ships no probe, so probing
    is best-effort and callers must tolerate None."""
    return shutil.which("ffprobe")


def _dimensions(aspect: str) -> tuple[int, int]:
    return _ASPECT_DIMENSIONS.get(aspect, _ASPECT_DIMENSIONS["9:16"])


@dataclass
class ClipSpec:
    start: float
    end: float
    out_path: str
    srt_path: str | None = None


def build_extract_audio_args(src_path: str, out_wav: str) -> list[str]:
    """ffmpeg args to extract a mono 16kHz wav (what whisper wants)."""
    return [
        ffmpeg_bin(), "-y", "-i", src_path,
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", out_wav,
    ]


def _crop_scale_filter(aspect: str) -> str:
    """Center smart-crop to the target aspect, then scale to output size.

    `crop=ih*aw/ah:ih` takes a centered column the height of the source and
    the correct aspect width, so the subject stays centered; then scale to the
    canonical output dimensions. No face model — documented as future work.
    """
    w, h = _dimensions(aspect)
    return f"crop=ih*{w}/{h}:ih,scale={w}:{h},setsar=1"


def _escape_srt_path(srt_path: str) -> str:
    # The subtitles filter needs ':' and '\' escaped inside the filtergraph.
    return srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_clip_args(src_path: str, spec: ClipSpec, aspect: str) -> list[str]:
    """ffmpeg args to cut one moment, reframe to `aspect`, and burn captions."""
    duration = max(0.1, spec.end - spec.start)
    vf = _crop_scale_filter(aspect)
    if spec.srt_path:
        vf += f",subtitles='{_escape_srt_path(spec.srt_path)}'"
    return [
        ffmpeg_bin(), "-y",
        "-ss", f"{spec.start:.2f}", "-i", src_path, "-t", f"{duration:.2f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        spec.out_path,
    ]


def _fmt_ts(seconds: float) -> str:
    """Seconds -> SRT timestamp HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0
    ms = round((seconds - int(seconds)) * 1000)
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d},{ms:03d}"


def build_srt(caption_lines: list[str], duration: float) -> str:
    """Lay caption lines evenly across the clip as sequential SRT cues."""
    lines = [c for c in caption_lines if c.strip()]
    if not lines:
        return ""
    span = duration / len(lines)
    cues: list[str] = []
    for i, text in enumerate(lines):
        start = i * span
        end = min(duration, (i + 1) * span)
        cues.append(f"{i + 1}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{text}\n")
    return "\n".join(cues)


def _run(args: list[str]) -> None:
    logger.info("ffmpeg: %s", " ".join(args[:6]) + " ...")
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()[-5:]
        raise RuntimeError("ffmpeg failed:\n" + "\n".join(tail))


def extract_audio(src_path: str, out_wav: str) -> None:
    _run(build_extract_audio_args(src_path, out_wav))


def render_clip(src_path: str, spec: ClipSpec, aspect: str) -> None:
    _run(build_clip_args(src_path, spec, aspect))


def probe_duration(src_path: str) -> float | None:
    """Best-effort source duration in seconds (None when ffprobe is absent)."""
    probe = ffprobe_bin()
    if not probe:
        return None
    args = [
        probe, "-v", "quiet", "-print_format", "json",
        "-show_format", src_path,
    ]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    try:
        return float(json.loads(proc.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
