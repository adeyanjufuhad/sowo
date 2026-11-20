"""WhatsApp Cloud API: check Meta's signature, read inbound messages, send replies.

Meta delivers every buyer message to POST /webhooks/whatsapp (app/routes_webhooks.py). We answer by calling
the Graph API's /messages endpoint, from the vendor's own business number (a message that came in on one
vendor's number is always answered from that number).
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 4096  # WhatsApp rejects longer text bodies

# Tests point this at an httpx.MockTransport; in production it stays None.
_transport_override: httpx.BaseTransport | None = None


@dataclass(frozen=True)
class InboundMessage:
    id: str
    phone_number_id: str  # the vendor's business number that received it
    phone: str
    name: str
    kind: str  # "text", "image", "audio", ...
    text: str  # empty unless kind == "text"
    media_id: str = ""  # for audio, image, document...: what fetch_media downloads
    mime_type: str = ""


@dataclass(frozen=True)
class DeliveryStatus:
    id: str
    status: str  # "sent", "delivered", "read" or "failed"
    recipient: str  # masked
    reason: str  # Meta's error for a failure, empty otherwise


def parse_statuses(payload: dict[str, Any]) -> list[DeliveryStatus]:
    """Delivery receipts for the messages we sent. Meta reports a failure here, not on our send call."""
    statuses: list[DeliveryStatus] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") if isinstance(change, dict) else None
            if not isinstance(value, dict):
                continue
            for raw in value.get("statuses") or []:
                if not isinstance(raw, dict) or not raw.get("id"):
                    continue
                first = next((e for e in raw.get("errors") or [] if isinstance(e, dict)), {})
                reason = str(first.get("title") or first.get("message") or "")
                if first.get("code"):
                    reason = f"{first['code']}: {reason}"
                statuses.append(
                    DeliveryStatus(
                        id=str(raw["id"]),
                        status=str(raw.get("status") or ""),
                        recipient=_mask(str(raw.get("recipient_id") or "")),
                        reason=reason,
                    )
                )
    return statuses


def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """Meta signs every webhook: X-Hub-Signature-256 is 'sha256=' + HMAC-SHA256(raw body, app secret)."""
    if not header or not app_secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256=").strip().lower())


def parse_inbound(payload: dict[str, Any]) -> list[InboundMessage]:
    """Buyer messages in a webhook payload. Delivery receipts and other events are ignored."""
    messages: list[InboundMessage] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") if isinstance(change, dict) else None
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata")
            phone_number_id = str(metadata.get("phone_number_id") or "") if isinstance(metadata, dict) else ""
            names = {
                contact.get("wa_id"): (contact.get("profile") or {}).get("name", "")
                for contact in value.get("contacts") or []
                if isinstance(contact, dict)
            }
            for raw in value.get("messages") or []:
                if not isinstance(raw, dict) or not raw.get("id") or not raw.get("from"):
                    continue
                kind = str(raw.get("type") or "unknown")
                body = (raw.get("text") or {}).get("body", "") if kind == "text" else ""
                media = raw.get(kind) if kind != "text" and isinstance(raw.get(kind), dict) else {}
                messages.append(
                    InboundMessage(
                        id=str(raw["id"]),
                        phone_number_id=phone_number_id,
                        phone=str(raw["from"]),
                        name=str(names.get(raw["from"]) or ""),
                        kind=kind,
                        text=str(body),
                        media_id=str(media.get("id") or ""),
                        mime_type=str(media.get("mime_type") or ""),
                    )
                )
    return messages


def is_configured(phone_number_id: str | None) -> bool:
    """Can we send from this number? It needs the platform's access token and a number to send from."""
    return bool(get_settings().whatsapp_access_token and phone_number_id)


def _mask(phone: str) -> str:
    return f"…{phone[-4:]}" if len(phone) > 4 else "…"


def _post(phone_number_id: str, path_suffix: str, payload: dict[str, Any]) -> bool:
    settings = get_settings()
    url = f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{phone_number_id}/{path_suffix}"
    try:
        with httpx.Client(timeout=15.0, transport=_transport_override) as client:
            response = client.post(
                url, json=payload, headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"}
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp %s failed: %s", path_suffix, exc)
        return False
    return True


def send_whatsapp_text(phone_number_id: str | None, phone: str, text: str) -> bool:
    """Send a text message from a vendor's number. Returns False (and logs) instead of raising, so a Meta outage
    never breaks us."""
    if not phone_number_id or not is_configured(phone_number_id):
        logger.info("WhatsApp not configured for this vendor; not sending to %s", _mask(phone))
        return False
    sent = _post(
        phone_number_id,
        "messages",
        {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text[:MAX_TEXT_LENGTH], "preview_url": True},
        },
    )
    if sent:
        logger.info("WhatsApp accepted a reply for %s", _mask(phone))
    return sent


def send_whatsapp_voice(phone_number_id: str | None, phone: str, audio: bytes, mime_type: str) -> bool:
    """Upload OGG/Opus audio and send it as a voice note. False (logged) on any failure, so the caller can fall back
    to text."""
    if not phone_number_id or not is_configured(phone_number_id):
        logger.info("WhatsApp not configured for this vendor; not sending a voice note to %s", _mask(phone))
        return False
    settings = get_settings()
    base = f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{phone_number_id}"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    try:
        with httpx.Client(timeout=30.0, transport=_transport_override) as client:
            upload = client.post(
                f"{base}/media",
                headers=headers,
                data={"messaging_product": "whatsapp", "type": mime_type},
                files={"file": ("voice.ogg", audio, mime_type)},
            )
            upload.raise_for_status()
            media_id = upload.json()["id"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.warning("WhatsApp voice upload failed: %s", exc)
        return False
    sent = _post(
        phone_number_id,
        "messages",
        {"messaging_product": "whatsapp", "to": phone, "type": "audio", "audio": {"id": str(media_id), "voice": True}},
    )
    if sent:
        logger.info("WhatsApp accepted a voice reply for %s", _mask(phone))
    return sent


class MediaTooLarge(Exception):
    """The file is bigger than we are willing to download."""


# Meta hands out download links on its own hosts only; anything else is not followed.
_MEDIA_HOSTS = ("fbsbx.com", "facebook.com", "whatsapp.net")


def fetch_media(media_id: str, max_bytes: int) -> tuple[bytes, str] | None:
    """Download a buyer's media file: ask the Graph API for its link, then fetch it with the platform's token.

    Returns (bytes, mime type), or None if it can't be had. Raises MediaTooLarge before or while downloading anything
    over `max_bytes`, so a huge file never fills memory.
    """
    settings = get_settings()
    if not media_id or not settings.whatsapp_access_token:
        return None
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    try:
        with httpx.Client(timeout=30.0, transport=_transport_override) as client:
            info = client.get(f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{media_id}", headers=headers)
            info.raise_for_status()
            meta = info.json()
            url = httpx.URL(str(meta.get("url") or ""))
            if url.scheme != "https" or not any(url.host == h or url.host.endswith("." + h) for h in _MEDIA_HOSTS):
                logger.warning("Refusing a WhatsApp media link on host %r", url.host)
                return None
            size = meta.get("file_size")
            if isinstance(size, int | str) and str(size).isdigit() and int(size) > max_bytes:
                raise MediaTooLarge
            data = bytearray()
            with client.stream("GET", url, headers=headers) as download:
                download.raise_for_status()
                for chunk in download.iter_bytes():
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise MediaTooLarge
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        logger.warning("WhatsApp media %s could not be downloaded: %s", media_id, exc)
        return None
    return bytes(data), str(meta.get("mime_type") or "")


def mark_read(phone_number_id: str | None, message_id: str) -> bool:
    """Show the buyer the blue ticks while Sowo is thinking. Best-effort."""
    if not phone_number_id or not is_configured(phone_number_id):
        return False
    return _post(
        phone_number_id, "messages", {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    )
