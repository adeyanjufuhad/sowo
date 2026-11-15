"""Speech to text. The agent never sees audio: a voice note becomes a transcript and is answered like typed text.

Add a provider (Spitch, Intron...) by writing a class with `transcribe(audio, mime) -> Transcript` and naming it
in `speech_to_text()`.
"""

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Whisper spells better with a hint of what it will hear: Nigerian Pidgin, haggling and Lagos places.
VOCABULARY_HINT = (
    "A Nigerian buyer on WhatsApp, in Pidgin or English. Abeg, wetin, how much, na, dey, una, oga, "
    "35k, 41k, naira, transfer, Ikeja, Yaba, Lekki, Surulere, Ajah."
)
# What Whisper accepts, by the file extension it reads the format from. Anything else is refused.
EXTENSIONS = {
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/webm": "webm",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
}

# Tests point this at an httpx.MockTransport; in production it stays None.
_transport_override: httpx.BaseTransport | None = None


@dataclass(frozen=True)
class Transcript:
    text: str
    duration_seconds: float | None = None
    language: str | None = None


class TranscriptionError(Exception):
    """The audio could not be turned into text: provider down, refused, or nothing intelligible."""


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes, mime: str) -> Transcript: ...


def base_mime(mime: str) -> str:
    """'audio/ogg; codecs=opus' -> 'audio/ogg'."""
    return mime.split(";")[0].strip().lower()


class GroqWhisper:
    """Whisper on Groq, through its OpenAI-compatible /audio/transcriptions endpoint."""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio: bytes, mime: str) -> Transcript:
        extension = EXTENSIONS.get(base_mime(mime))
        if extension is None:
            raise TranscriptionError(f"Unsupported audio type {mime!r}")
        try:
            with httpx.Client(timeout=30.0, transport=_transport_override) as client:
                response = client.post(
                    f"{GROQ_BASE_URL}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={
                        "model": self.model,
                        "response_format": "verbose_json",
                        "temperature": "0",
                        "prompt": VOCABULARY_HINT,
                    },
                    files={"file": (f"voice.{extension}", audio, base_mime(mime))},
                )
                response.raise_for_status()
                body: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TranscriptionError(f"Groq transcription failed: {exc}") from exc
        text = str(body.get("text") or "").strip() if isinstance(body, dict) else ""
        if not text:
            raise TranscriptionError("Groq heard nothing in the voice note")
        duration = body.get("duration")
        return Transcript(
            text=text,
            duration_seconds=float(duration) if isinstance(duration, int | float) else None,
            language=str(body["language"]) if body.get("language") else None,
        )


def speech_to_text(settings: Settings) -> SpeechToText | None:
    """The configured provider, or None when voice notes are off (no provider, or no key)."""
    if settings.stt_provider == "groq":
        key = settings.stt_api_key or (settings.llm_api_key if "api.groq.com" in settings.llm_base_url else "")
        if key:
            return GroqWhisper(key, settings.stt_model)
    return None
