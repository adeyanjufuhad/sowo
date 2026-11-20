"""Mirror mode: a buyer who sends a voice note hears Sowo's reply as a voice note, when that is safe.

Only a reply the guard has passed is spoken. Payment details (bank account, payment link) always go as text, so
the buyer can copy them, and nothing that asks for a code, PIN, BVN or password is ever said aloud.
"""

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Conversation, Message, MessageRole, Vendor, VoiceNote, VoiceStatus
from app.services import guard
from app.services.agent import AgentReply, _allowed_amounts, _has_paid_order
from app.services.shield.rules import asks_for_secrets
from app.services.voice.tts import SpeechError, text_to_speech

logger = logging.getLogger(__name__)

_PAYMENT_DETAILS = re.compile(r"https?://|\b\d{10}\b|\baccount (?:number|name)\b", re.IGNORECASE)


def _buyer_spoke(session: Session, conversation: Conversation, before: Message) -> bool:
    latest = session.scalar(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.BUYER,
            Message.created_at < before.created_at,
        )
        .order_by(Message.created_at.desc())
    )
    return latest is not None and latest.kind == "voice" and latest.voice_status == VoiceStatus.TRANSCRIBED.value


def speakable(session: Session, conversation: Conversation, reply: AgentReply) -> bool:
    """The guard's checks again, on the exact words that would be spoken, plus the voice-only rules."""
    text = reply.text
    if reply.used_fallback or not text.strip():
        return False  # the model's own words failed the guard: send the server's text, say nothing
    if any(call.get("tool") == "request_payment" for call in reply.tool_calls) or _PAYMENT_DETAILS.search(text):
        return False
    if guard.find_unbacked_amounts(text, _allowed_amounts(session, conversation, reply.tool_calls)):
        return False
    if not _has_paid_order(session, conversation) and guard.claims_payment_received(text):
        return False
    return asks_for_secrets(text) is None


def speak_reply(
    session: Session, conversation: Conversation, message: Message, reply: AgentReply, settings: Settings
) -> bool:
    """Give Sowo's reply `message` a voice note when mirror mode applies. True if it now has one. Commits."""
    vendor = session.get(Vendor, conversation.vendor_id)
    provider = text_to_speech(settings)
    if vendor is None or not vendor.voice_replies or provider is None:
        return False
    if not _buyer_spoke(session, conversation, message) or not speakable(session, conversation, reply):
        return False
    try:
        speech = provider.synthesize(message.text)
    except SpeechError as exc:
        logger.warning("Voice reply not spoken, sending text: %s", exc)
        return False
    note = VoiceNote(conversation_id=conversation.id, mime_type=speech.mime_type, data=speech.audio)
    session.add(note)
    session.flush()
    message.kind, message.voice_status, message.voice_note_id = "voice", VoiceStatus.TRANSCRIBED.value, note.id
    session.commit()
    return True
