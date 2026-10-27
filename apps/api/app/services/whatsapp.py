"""WhatsApp Cloud API: check Meta's signature, read inbound messages, send replies.

Meta delivers every buyer message to POST /webhooks/whatsapp (app/routes_webhooks.py). We answer by calling
the Graph API's /messages endpoint with the access token for our business phone number.
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
    phone: str
    name: str
    kind: str  # "text", "image", "audio", ...
    text: str  # empty unless kind == "text"


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
                messages.append(
                    InboundMessage(
                        id=str(raw["id"]),
                        phone=str(raw["from"]),
                        name=str(names.get(raw["from"]) or ""),
                        kind=kind,
                        text=str(body),
                    )
                )
    return messages


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)


def _mask(phone: str) -> str:
    return f"…{phone[-4:]}" if len(phone) > 4 else "…"


def _post(path_suffix: str, payload: dict[str, Any]) -> bool:
    settings = get_settings()
    url = f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{settings.whatsapp_phone_number_id}/{path_suffix}"
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


def send_whatsapp_text(phone: str, text: str) -> bool:
    """Send a text message. Returns False (and logs) instead of raising, so a Meta outage never breaks us."""
    if not is_configured():
        logger.info("WhatsApp not configured; not sending to %s", _mask(phone))
        return False
    return _post(
        "messages",
        {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text[:MAX_TEXT_LENGTH], "preview_url": True},
        },
    )


def mark_read(message_id: str) -> bool:
    """Show the buyer the blue ticks while Sowo is thinking. Best-effort."""
    if not is_configured():
        return False
    return _post("messages", {"messaging_product": "whatsapp", "status": "read", "message_id": message_id})
