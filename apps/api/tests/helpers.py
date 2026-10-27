"""Test doubles for the model."""

import copy
import hashlib
import hmac
import json
from collections.abc import Callable
from typing import Any

from app.deps import get_chat_model
from app.main import app

VENDOR_EMAIL = "ada@example.com"
VENDOR_PASSWORD = "correct horse battery"
APP_SECRET = "meta-app-secret"
PAYSTACK_SECRET = "paystack-test-secret"
VERIFY_TOKEN = "verify-me"
VENDOR_PHONE = "2348099999999"
WHATSAPP_NUMBER_ID = "1555000111"  # Ada's WhatsApp business number, as Meta's Cloud API names it
BUYER_PHONE = "2348012345678"
LOAFERS_FLOOR_KOBO = 3_876_500  # distinctive, so a leak is easy to spot in any text

Turn = dict[str, Any] | Callable[[list[dict[str, Any]]], dict[str, Any]]


class ScriptedModel:
    """Plays Qwen3: each chat() call returns the next scripted message.

    A turn can be a function of the messages so far, for replies that depend on earlier tool results
    (the quote id, the payment link). Everything the agent sends is kept in `requests`.
    """

    def __init__(self, *turns: Turn) -> None:
        self._turns = list(turns)
        self.requests: list[dict[str, Any]] = []

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        self.requests.append({"messages": copy.deepcopy(messages), "tools": tools})
        if not self._turns:
            raise AssertionError("The agent asked the model for more turns than the test scripted")
        turn = self._turns.pop(0)
        return turn(messages) if callable(turn) else turn

    @property
    def everything_sent(self) -> str:
        """All the text the model was ever shown, as one string."""
        return json.dumps(self.requests, ensure_ascii=False)

    @property
    def turns_left(self) -> int:
        return len(self._turns)


def sign_in_vendor(session: Any, vendor: Any, email: str = VENDOR_EMAIL, password: str = VENDOR_PASSWORD) -> str:
    """Give the vendor a login and start a session. Returns the bearer token a dashboard request needs."""
    from app.services import auth

    vendor.email = email
    vendor.password_hash = auth.hash_password(password)
    session.commit()
    token, _ = auth.create_session(session, vendor)
    return token


def say(text: str) -> dict[str, Any]:
    return {"role": "assistant", "content": text}


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


def last_tool_result(messages: list[dict[str, Any]], tool_name: str) -> dict[str, Any]:
    """What a tool told the model most recently, as the model saw it."""
    for message in reversed(messages):
        if message.get("role") == "tool" and message.get("tool_name") == tool_name:
            return json.loads(message["content"])
    raise AssertionError(f"The model was never given a result from {tool_name}")


def use_model(model: object) -> None:
    """Make the API's routes talk to a scripted model."""
    app.dependency_overrides[get_chat_model] = lambda: model


def signed(payload: dict[str, Any], secret: str = APP_SECRET) -> tuple[bytes, dict[str, str]]:
    """A webhook body and its X-Hub-Signature-256 header, the way Meta sends them."""
    raw = json.dumps(payload).encode()
    digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {"X-Hub-Signature-256": f"sha256={digest}", "Content-Type": "application/json"}


def paystack_signed(payload: dict[str, Any], secret: str = PAYSTACK_SECRET) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload).encode()
    digest = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()
    return raw, {"X-Paystack-Signature": digest, "Content-Type": "application/json"}


def whatsapp_payload(
    text: str = "Hello",
    *,
    message_id: str = "wamid.in1",
    phone: str = BUYER_PHONE,
    name: str = "Funke",
    phone_number_id: str = WHATSAPP_NUMBER_ID,
) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"profile": {"name": name}, "wa_id": phone}],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": message_id,
                                    "timestamp": "1761500000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
