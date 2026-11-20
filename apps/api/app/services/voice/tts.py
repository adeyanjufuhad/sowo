"""Text to speech, for answering a voice note with a voice note. It only ever speaks text the server already approved.

Add a provider by writing a class with `synthesize(text) -> Speech` and naming it in `text_to_speech()`. WhatsApp
plays a voice note only from OGG/Opus, so a provider should return that (or have its audio converted first).
"""

import logging
from dataclasses import dataclass
from typing import Protocol
from xml.sax.saxutils import escape

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

# Tests point this at an httpx.MockTransport; in production it stays None.
_transport_override: httpx.BaseTransport | None = None


@dataclass(frozen=True)
class Speech:
    audio: bytes
    mime_type: str


class SpeechError(Exception):
    """The provider couldn't speak the text. The reply goes out as text instead."""


class TextToSpeech(Protocol):
    def synthesize(self, text: str) -> Speech: ...


class AzureSpeech:
    """Azure Speech's neural voices. en-NG-EzinneNeural and en-NG-AbeoNeural speak Nigerian English."""

    def __init__(self, key: str, region: str, voice: str) -> None:
        self.key, self.region, self.voice = key, region, voice

    def synthesize(self, text: str) -> Speech:
        language = "-".join(self.voice.split("-")[:2]) or "en-NG"
        ssml = (
            f"<speak version='1.0' xml:lang='{escape(language)}'>"
            f"<voice name='{escape(self.voice)}'>{escape(text)}</voice></speak>"
        )
        try:
            with httpx.Client(timeout=20.0, transport=_transport_override) as client:
                response = client.post(
                    f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1",
                    headers={
                        "Ocp-Apim-Subscription-Key": self.key,
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": "ogg-24khz-16bit-mono-opus",
                        "User-Agent": "sowo-api",
                    },
                    content=ssml.encode(),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SpeechError(f"Azure Speech failed: {exc}") from exc
        if not response.content:
            raise SpeechError("Azure Speech returned no audio")
        return Speech(response.content, "audio/ogg")


def text_to_speech(settings: Settings) -> TextToSpeech | None:
    """The configured provider, or None when voice replies are off (no provider, key or region)."""
    if settings.tts_provider == "azure" and settings.azure_speech_key and settings.azure_speech_region:
        return AzureSpeech(settings.azure_speech_key, settings.azure_speech_region, settings.tts_voice)
    return None
