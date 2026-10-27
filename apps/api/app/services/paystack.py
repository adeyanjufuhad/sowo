"""Paystack: create a payment link, and check the signature on the webhook that confirms it.

An order only counts as paid when Paystack's signed webhook says so (see app/routes_webhooks.py). A
buyer's message or screenshot never marks anything paid.
"""

import hashlib
import hmac
import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Tests point this at an httpx.MockTransport; in production it stays None.
_transport_override: httpx.BaseTransport | None = None


class PaystackError(RuntimeError):
    """Paystack was unreachable or refused to create the payment link."""


def is_configured() -> bool:
    return bool(get_settings().paystack_secret_key)


def buyer_email(phone: str) -> str:
    """Paystack needs an email for every payer; WhatsApp buyers have none, so make a placeholder."""
    local = re.sub(r"\D", "", phone) or "buyer"
    return f"{local}@{get_settings().paystack_customer_email_domain}"


def initialize_transaction(
    *, reference: str, amount_kobo: int, email: str, metadata: dict[str, Any] | None = None
) -> str:
    """Create a Paystack payment page for an order and return its URL."""
    settings = get_settings()
    payload: dict[str, Any] = {
        "email": email,
        "amount": amount_kobo,
        "currency": "NGN",
        "reference": reference,
        "metadata": metadata or {},
    }
    if settings.paystack_callback_url:
        payload["callback_url"] = settings.paystack_callback_url
    try:
        with httpx.Client(
            base_url=settings.paystack_base_url, timeout=15.0, transport=_transport_override
        ) as client:
            response = client.post(
                "/transaction/initialize",
                json=payload,
                headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
            )
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Paystack initialize failed for %s: %s", reference, exc)
        raise PaystackError("Could not create the payment link") from exc
    data = body.get("data") if isinstance(body, dict) else None
    url = data.get("authorization_url") if isinstance(data, dict) else None
    if not body.get("status") or not isinstance(url, str) or not url:
        raise PaystackError("Paystack did not return a payment link")
    return url


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """Paystack signs each webhook with HMAC-SHA512 of the raw body, keyed with your secret key."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())
