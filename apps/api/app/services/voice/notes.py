"""A buyer's voice note, from audio to transcript. Shared by the WhatsApp webhook and the /try simulator.

The message is saved first (kind "voice", status PENDING) so a duplicate delivery is still caught while we listen;
`hear` then stores the audio, transcribes it and puts the transcript in the message's text. A transcript is only
words from the buyer: it goes to the agent like typed text, and the server still decides every amount.
"""

import logging

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Message, VoiceNote, VoiceStatus
from app.services.voice.stt import EXTENSIONS, TranscriptionError, base_mime, speech_to_text

logger = logging.getLogger(__name__)


def hear(session: Session, message: Message, audio: bytes, mime: str, settings: Settings) -> VoiceStatus:
    """Store and transcribe `audio` for `message`. Never raises: a failure becomes a status the buyer is told about."""
    status = _transcribe(session, message, audio, mime, settings)
    message.voice_status = status.value
    session.commit()
    return status


def _transcribe(session: Session, message: Message, audio: bytes, mime: str, settings: Settings) -> VoiceStatus:
    if len(audio) > settings.voice_max_bytes:
        return VoiceStatus.TOO_LONG
    if not audio or base_mime(mime) not in EXTENSIONS:
        logger.info("Voice note refused: %d bytes of %r", len(audio), mime)
        return VoiceStatus.FAILED
    note = VoiceNote(conversation_id=message.conversation_id, mime_type=base_mime(mime), data=audio)
    session.add(note)
    session.flush()
    message.voice_note_id = note.id

    provider = speech_to_text(settings)
    if provider is None:
        return VoiceStatus.FAILED
    try:
        transcript = provider.transcribe(audio, mime)
    except TranscriptionError as exc:
        logger.warning("Voice note not transcribed: %s", exc)
        return VoiceStatus.FAILED
    if transcript.duration_seconds is not None:
        note.duration_ms = round(transcript.duration_seconds * 1000)
        if transcript.duration_seconds > settings.voice_max_seconds:
            return VoiceStatus.TOO_LONG
    message.text = transcript.text
    return VoiceStatus.TRANSCRIBED


def cant_hear_reply(status: VoiceStatus, *, pidgin: bool, max_seconds: int) -> str:
    """What Sowo says when it can't use a voice note. Written by us, not the model."""
    minutes = max(1, max_seconds // 60)
    if status == VoiceStatus.TOO_LONG:
        if pidgin:
            return f"This voice note too long for me o. Abeg type am, or send shorter one (under {minutes} minutes)."
        return f"That voice note is a bit long for me. Please type it, or send a shorter one (under {minutes} minutes)."
    if pidgin:
        return "Abeg, I no fit hear this voice note well. Type wetin you want for me?"
    return "Sorry, I couldn't make out that voice note. Could you type it for me?"
