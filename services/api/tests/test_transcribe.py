"""No-network tests for the transcription adapter's OpenAI backend.

The OpenAI Whisper API (`openai>=1.0`) returns a result whose `.segments` is a
list of typed `TranscriptionSegment` Pydantic objects — fields are attributes,
not dict keys. We build real `TranscriptionSegment` objects and inject a fake
`openai.OpenAI` client so the network boundary is never crossed, guarding the
parser against a regression back to dict subscripting (`seg["start"]`).
"""

import types

import pytest
from openai.types.audio.transcription_segment import TranscriptionSegment

from app.config import settings
from app.repo import transcribe


def _segment(start: float, end: float, text: str) -> TranscriptionSegment:
    """A faithful typed segment, matching what the Whisper API deserializes to."""
    return TranscriptionSegment(
        id=0,
        seek=0,
        start=start,
        end=end,
        text=text,
        tokens=[],
        temperature=0.0,
        avg_logprob=0.0,
        compression_ratio=1.0,
        no_speech_prob=0.0,
    )


class _FakeTranscriptions:
    def __init__(self, segments):
        self._segments = segments

    def create(self, **_payload):
        return types.SimpleNamespace(segments=self._segments)


class _FakeClient:
    """Stand-in for openai.OpenAI — never touches the network."""

    def __init__(self, *_args, segments=None, **_kwargs):
        self.audio = types.SimpleNamespace(
            transcriptions=_FakeTranscriptions(segments or [])
        )


def test_transcribe_openai_parses_typed_segments(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "transcription_backend", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    segments = [
        _segment(0.0, 5.0, " Welcome to the show. "),
        _segment(5.0, 30.0, "Here is the most important idea."),
    ]

    import openai

    monkeypatch.setattr(
        openai, "OpenAI", lambda *a, **k: _FakeClient(segments=segments)
    )

    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"\x00\x00")

    out = transcribe.transcribe_audio(str(audio))

    assert out == [
        {"start": 0.0, "end": 5.0, "text": "Welcome to the show."},
        {"start": 5.0, "end": 30.0, "text": "Here is the most important idea."},
    ]


def test_transcribe_openai_requires_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "transcription_backend", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")

    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"\x00\x00")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        transcribe.transcribe_audio(str(audio))
