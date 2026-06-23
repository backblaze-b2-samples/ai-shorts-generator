"""Transcription adapter.

Local & keyless by default (faster-whisper). An optional remote backend
(`TRANSCRIPTION_BACKEND=openai`) reuses the SAME `OPENAI_API_KEY` as the
moment-detection step, so the whole sample needs exactly one external key.

This lives in repo/ because it owns a heavy external model (whisper) / a
remote provider client — the layering rule keeps that out of service/runtime.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


# A transcript segment: a contiguous span of speech with timestamps. `words`
# is optional fine-grained word timing used to tighten clip boundaries.
TranscriptSegment = dict  # {"start": float, "end": float, "text": str}


def transcribe_audio(audio_path: str) -> list[TranscriptSegment]:
    """Transcribe a local audio/video file into timestamped segments.

    Dispatches on `TRANSCRIPTION_BACKEND`. The default (`local`) loads a
    faster-whisper model lazily so importing this module never pulls heavy
    deps at process start.
    """
    backend = settings.transcription_backend.lower()
    if backend == "openai":
        return _transcribe_openai(audio_path)
    return _transcribe_local(audio_path)


def _transcribe_local(audio_path: str) -> list[TranscriptSegment]:
    # Imported lazily: faster-whisper is a large dependency and not needed
    # until a transcription actually runs.
    from faster_whisper import WhisperModel

    logger.info("Transcribing locally with whisper model=%s", settings.whisper_model)
    # CPU + int8 keeps the demo runnable on a laptop with no GPU.
    model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path, vad_filter=True)
    out: list[TranscriptSegment] = []
    for seg in segments:
        out.append(
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": seg.text.strip(),
            }
        )
    logger.info("Transcription complete: %d segments", len(out))
    return out


def _transcribe_openai(audio_path: str) -> list[TranscriptSegment]:
    """Remote Whisper via the OpenAI API. Reuses OPENAI_API_KEY."""
    import openai

    if not settings.openai_api_key:
        raise RuntimeError(
            "TRANSCRIPTION_BACKEND=openai requires OPENAI_API_KEY to be set."
        )
    client = openai.OpenAI(api_key=settings.openai_api_key)
    logger.info("Transcribing via OpenAI Whisper API")
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    out: list[TranscriptSegment] = []
    for seg in getattr(result, "segments", []) or []:
        out.append(
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": str(seg["text"]).strip(),
            }
        )
    logger.info("Remote transcription complete: %d segments", len(out))
    return out
