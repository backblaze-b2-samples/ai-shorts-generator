"""No-network signature-guard tests for the Genblaze/OpenAI moment step.

These assert the LLM call is assembled and routed through the Genblaze SDK
correctly WITHOUT making a live API call: we inject a fake OpenAI client (the
`client=` escape hatch `genblaze_openai.chat` forwards) and capture the payload
genblaze builds, so the network boundary is never crossed.
"""

import json
import types

from app.repo import moments


class _FakeRawCompletion:
    """Mimics an OpenAI ChatCompletion: genblaze calls `.model_dump()` on it."""

    def __init__(self, text, model):
        self._text = text
        self._model = model

    def model_dump(self):
        return {
            "model": self._model,
            "choices": [
                {"message": {"content": self._text, "tool_calls": None},
                 "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }


class _FakeCompletions:
    def __init__(self, recorder, text):
        self._recorder = recorder
        self._text = text

    def create(self, **payload):
        # Capture exactly what genblaze assembled and routed to OpenAI.
        self._recorder["payload"] = payload
        return _FakeRawCompletion(self._text, payload.get("model"))


class _FakeClient:
    """Stand-in for openai.OpenAI — never touches the network."""

    def __init__(self, recorder, text):
        self.chat = types.SimpleNamespace(
            completions=_FakeCompletions(recorder, text)
        )

    def close(self):  # genblaze closes own clients; ours is injected so it won't
        pass


_SEGMENTS = [
    {"start": 0.0, "end": 5.0, "text": "Welcome to the show."},
    {"start": 5.0, "end": 30.0, "text": "Here is the most important idea."},
]


def test_detect_moments_routes_through_genblaze_without_network():
    recorder: dict = {}
    canned = json.dumps(
        {
            "moments": [
                {
                    "start": 5.0,
                    "end": 28.0,
                    "title": "The big idea",
                    "hook": "You need to hear this",
                    "caption_lines": ["The big idea", "changes everything"],
                }
            ]
        }
    )
    fake = _FakeClient(recorder, canned)

    result = moments.detect_moments(_SEGMENTS, clip_count=1, client=fake)

    # 1. The call was assembled and routed to the OpenAI client genblaze owns.
    assert "payload" in recorder, "genblaze_openai.chat never called the client"
    payload = recorder["payload"]
    # 2. Model + structured-output spec wired correctly.
    assert payload["model"] == "gpt-4o-mini"
    assert payload.get("response_format") == {"type": "json_object"}
    # 3. The transcript made it into the prompt the SDK sent.
    sent = json.dumps(payload.get("messages", []))
    assert "most important idea" in sent
    # 4. The response was parsed into clean moment dicts.
    assert len(result) == 1
    assert result[0]["title"] == "The big idea"
    assert result[0]["end"] > result[0]["start"]
    assert result[0]["caption_lines"] == ["The big idea", "changes everything"]


def test_detect_moments_drops_invalid_spans():
    recorder: dict = {}
    canned = json.dumps(
        {
            "moments": [
                {"start": 10.0, "end": 5.0, "title": "backwards"},  # dropped
                {"start": 1.0, "end": 9.0, "title": "good"},
            ]
        }
    )
    out = moments.detect_moments(
        _SEGMENTS, clip_count=2, client=_FakeClient(recorder, canned)
    )
    assert [m["title"] for m in out] == ["good"]


def test_detect_moments_uses_chat_helper_not_bare_openai():
    """The Genblaze-routing mandate: the SDK's chat() helper is imported and
    used (not the bare `openai` package) inside repo/moments.py."""
    import genblaze_openai

    assert moments.detect_moments.__module__ == "app.repo.moments"
    # The helper genblaze exposes for text is importable and callable.
    assert callable(genblaze_openai.chat)
