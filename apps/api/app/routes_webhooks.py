"""Webhooks: WhatsApp (buyer messages) and Paystack (payment confirmations).

Both are signed by the sender, and both are answered with 200 straight away: the real work (a model call,
a WhatsApp send) runs in the background so the sender never times out and retries.
"""

import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.deps import ChatModelDependency
from app.services import flow, paystack, whatsapp

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/webhooks/whatsapp")
def verify_whatsapp_webhook(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Meta calls this once when you register the webhook, and expects the challenge echoed back."""
    expected = get_settings().whatsapp_verify_token
    if mode == "subscribe" and expected and token and challenge is not None and hmac.compare_digest(token, expected):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


def _json_body(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Body must be JSON") from exc
    return payload if isinstance(payload, dict) else {}


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(
    request: Request, background: BackgroundTasks, model: ChatModelDependency
) -> dict[str, str]:
    secret = get_settings().whatsapp_app_secret
    if not secret:
        raise HTTPException(status_code=503, detail="WhatsApp is not configured")
    raw = await request.body()
    if not whatsapp.verify_signature(raw, request.headers.get("x-hub-signature-256"), secret):
        raise HTTPException(status_code=403, detail="Invalid signature")
    payload = _json_body(raw)
    messages = whatsapp.parse_inbound(payload)
    if messages:
        background.add_task(flow.process_inbound, messages, model)
    for status in whatsapp.parse_statuses(payload):
        if status.status == "failed":
            logger.warning("WhatsApp delivery to %s failed: %s", status.recipient, status.reason or "no reason given")
    return {"status": "received"}


@router.post("/webhooks/paystack")
async def receive_paystack_webhook(request: Request, background: BackgroundTasks) -> dict[str, str]:
    raw = await request.body()
    if not paystack.verify_signature(raw, request.headers.get("x-paystack-signature"), get_settings().paystack_secret_key):
        raise HTTPException(status_code=403, detail="Invalid signature")
    payload = _json_body(raw)
    data = payload.get("data")
    if payload.get("event") == "charge.success" and isinstance(data, dict):
        background.add_task(flow.process_charge_success, data)
    return {"status": "received"}
