"""Core AI step: pick the most engaging moments and write captions.

Routes the LLM call through the **Genblaze SDK** (`genblaze-core` +
`genblaze-openai`) via its text helper `genblaze_openai.chat()`. The
`Pipeline().step(Provider())` classes in genblaze-openai (Dalle/Sora/TTS) are
image/video/audio modalities; the SDK's text/LLM interface is the `chat()`
helper, so that is what a text task uses. Using it IS routing through the
Genblaze SDK — never the bare `openai` package.

All genblaze imports stay in repo/ to honor the layering rule
(tests/test_structure.py enforces boto3/genblaze/whisper only in repo/).
"""

import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Cap how much transcript we send. A 60-min podcast (~12-15k tokens) fits well
# inside gpt-4o-mini's context, but we trim defensively for very long inputs.
_MAX_TRANSCRIPT_CHARS = 48_000

# A clamped moment shorter than this (after bounding to the source duration) is
# too small to be a usable short, so it's dropped rather than rendered.
_MIN_CLIP_SECONDS = 1.0

_SYSTEM = (
    "You are a short-form video editor. Given a timestamped transcript of a "
    "long video, pick the most engaging, self-contained moments to cut into "
    "vertical shorts. Each moment must be 20-60 seconds long and start/end on "
    "a natural sentence boundary. Write a punchy title, a one-line hook, and "
    "2-4 short caption lines (each <= 8 words) that will be burned onto the "
    "clip. Respond with STRICT JSON only."
)

# Looser brief used for a single retry when the strict pass returns nothing —
# trades polish for recall so a video with any speech still yields a clip.
_SYSTEM_RELAXED = (
    "You are a short-form video editor. Given a timestamped transcript of a "
    "long video, pick ANY usable moments to cut into vertical shorts — rough "
    "ones are fine. Each moment should be roughly 10-90 seconds long; sentence "
    "boundaries are a nice-to-have, not a requirement. If the transcript has "
    "any speech at all, you MUST return at least one moment. Write a punchy "
    "title, a one-line hook, and 2-4 short caption lines (each <= 8 words) that "
    "will be burned onto the clip. Respond with STRICT JSON only."
)


def _build_prompt(segments: list[dict], clip_count: int) -> str:
    lines = [f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segments]
    transcript = "\n".join(lines)[:_MAX_TRANSCRIPT_CHARS]
    return (
        f"Pick the {clip_count} best moments from this transcript.\n\n"
        f"Return JSON of the exact shape:\n"
        '{"moments": [{"start": <sec float>, "end": <sec float>, '
        '"title": <str>, "hook": <str>, "caption_lines": [<str>, ...]}]}\n\n'
        f"Transcript:\n{transcript}"
    )


def _coerce(payload: dict, max_end: float | None = None) -> list[dict]:
    """Normalize and validate the model's JSON into clean moment dicts.

    When `max_end` (the source duration in seconds) is given, moments that start
    at or past the end of the video are dropped and an overshooting `end` is
    clamped to the duration — guarding against model-hallucinated timestamps
    that would otherwise fail (or silently truncate) at the render step.
    """
    moments: list[dict] = []
    for m in payload.get("moments", []):
        try:
            start = float(m["start"])
            end = float(m["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if end <= start:
            continue
        if max_end is not None:
            if start >= max_end:
                continue
            end = min(end, max_end)
            if end - start < _MIN_CLIP_SECONDS:
                continue
        caption_lines = [str(c) for c in m.get("caption_lines", []) if str(c).strip()]
        moments.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "title": str(m.get("title", "")).strip() or "Untitled clip",
                "hook": str(m.get("hook", "")).strip(),
                "caption_lines": caption_lines,
            }
        )
    return moments


def detect_moments(
    segments: list[dict],
    clip_count: int | None = None,
    *,
    relaxed: bool = False,
    max_end: float | None = None,
    client: Any = None,
) -> list[dict]:
    """Score engaging moments + write captions via Genblaze's OpenAI text helper.

    `relaxed` swaps in a looser brief (wider duration band, sentence boundaries
    optional) for a single retry when the strict first pass returns nothing.
    `max_end` is the source duration in seconds; when given, moments are bounded
    to it (see `_coerce`).

    `client` is an OpenAI-client escape hatch forwarded to `genblaze_openai.chat`
    — used by the no-network signature-guard test to assert the call is
    assembled correctly without hitting the network. In production it stays
    None and the helper builds its own client from OPENAI_API_KEY.
    """
    # Genblaze SDK import — contained in repo/ per layering rules.
    from genblaze_openai import chat

    count = clip_count or settings.clips_per_video
    if not settings.openai_api_key and client is None:
        raise RuntimeError(
            "Moment detection requires OPENAI_API_KEY. Add it to .env (see "
            ".env.example) — this is the app's one external AI key."
        )

    prompt = _build_prompt(segments, count)
    logger.info(
        "Detecting moments via Genblaze/OpenAI model=%s (relaxed=%s)",
        settings.shorts_model,
        relaxed,
    )
    response = chat(
        model=settings.shorts_model,
        prompt=prompt,
        system=_SYSTEM_RELAXED if relaxed else _SYSTEM,
        response_format={"type": "json_object"},
        temperature=0.4,
        max_tokens=2000,
        api_key=settings.openai_api_key or None,
        client=client,
    )
    try:
        payload = json.loads(response.text)
    except (json.JSONDecodeError, TypeError) as e:
        raise RuntimeError(f"Moment model returned non-JSON output: {e}") from e

    moments = _coerce(payload, max_end=max_end)
    logger.info(
        "Detected %d moments (tokens_in=%s tokens_out=%s cost_usd=%s)",
        len(moments),
        getattr(response, "tokens_in", None),
        getattr(response, "tokens_out", None),
        getattr(response, "cost_usd", None),
    )
    return moments
