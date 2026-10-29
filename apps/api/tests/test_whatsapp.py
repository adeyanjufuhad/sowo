"""WhatsApp: Meta's handshake, signature checks, and a buyer's message all the way to Sowo's reply."""

import json
import logging
from typing import Any

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import (
    BUYER_PHONE,
    VENDOR_PHONE,
    VERIFY_TOKEN,
    ScriptedModel,
    call,
    say,
    signed,
    use_model,
    whatsapp_payload,
)
from scenarios import new_chat
from sqlalchemy import select

from app.config import get_settings
from app.models import Conversation, ConversationStatus, Message, MessageRole
from app.services import whatsapp
from app.services.flow import NON_TEXT_REPLY, TROUBLE_REPLY
from app.services.ollama import OllamaError


def post_webhook(client: TestClient, payload: dict[str, Any]) -> httpx.Response:
    raw, headers = signed(payload)
    return client.post("/webhooks/whatsapp", content=raw, headers=headers)


def messages_in(env: Env, phone: str = BUYER_PHONE) -> list[tuple[MessageRole, str]]:
    with env.session() as session:
        conversation = session.scalar(select(Conversation).where(Conversation.customer_phone == phone))
        assert conversation is not None
        rows = session.scalars(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)
        )
        return [(row.role, row.text) for row in rows]


# -- signature -----------------------------------------------------------------------------------------


def test_signature_check() -> None:
    raw, headers = signed({"a": 1})
    header = headers["X-Hub-Signature-256"]
    assert whatsapp.verify_signature(raw, header, "meta-app-secret")
    assert not whatsapp.verify_signature(raw, header, "another-secret")
    assert not whatsapp.verify_signature(raw + b" ", header, "meta-app-secret")
    assert not whatsapp.verify_signature(raw, None, "meta-app-secret")
    assert not whatsapp.verify_signature(raw, header.removeprefix("sha256="), "meta-app-secret")
    assert not whatsapp.verify_signature(raw, header, "")


# -- Meta's one-off verification handshake -------------------------------------------------------------


def test_meta_verification_handshake_echoes_the_challenge(client: TestClient) -> None:
    response = client.get(
        "/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "1158201444"},
    )
    assert response.status_code == 200 and response.text == "1158201444"


@pytest.mark.parametrize(
    "params",
    [
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"},
        {"hub.mode": "unsubscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "1"},
        {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN},
        {},
    ],
)
def test_verification_refuses_wrong_or_incomplete_requests(client: TestClient, params: dict[str, str]) -> None:
    assert client.get("/webhooks/whatsapp", params=params).status_code == 403


def test_verification_is_off_until_a_token_is_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "")
    get_settings.cache_clear()
    params = {"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"}
    assert client.get("/webhooks/whatsapp", params=params).status_code == 403


# -- inbound messages ----------------------------------------------------------------------------------


def test_unsigned_or_badly_signed_deliveries_are_refused(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel())
    payload = whatsapp_payload()
    assert client.post("/webhooks/whatsapp", json=payload).status_code == 403
    raw, headers = signed(payload, secret="not-meta")
    assert client.post("/webhooks/whatsapp", content=raw, headers=headers).status_code == 403
    assert env.graph == []


def test_deliveries_are_refused_until_an_app_secret_is_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "")
    get_settings.cache_clear()
    raw, headers = signed(whatsapp_payload(), secret="")
    assert client.post("/webhooks/whatsapp", content=raw, headers=headers).status_code == 503


def test_a_signed_body_that_is_not_json_is_a_bad_request(client: TestClient) -> None:
    import hashlib
    import hmac

    raw = b"not json"
    digest = hmac.new(b"meta-app-secret", raw, hashlib.sha256).hexdigest()
    response = client.post("/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": f"sha256={digest}"})
    assert response.status_code == 400


def test_a_buyer_message_gets_a_reply_over_whatsapp(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel(say("Hello Funke! What are you looking for today?")))

    response = post_webhook(client, whatsapp_payload("Hello"))

    assert response.status_code == 200 and response.json() == {"status": "received"}
    assert messages_in(env) == [
        (MessageRole.BUYER, "Hello"),
        (MessageRole.AI, "Hello Funke! What are you looking for today?"),
    ]
    conversation = env.conversation()
    assert conversation.customer_name == "Funke" and conversation.greeted and not conversation.is_simulator

    read_receipt, reply = env.graph
    assert read_receipt["json"] == {"messaging_product": "whatsapp", "status": "read", "message_id": "wamid.in1"}
    assert reply["url"] == "https://graph.facebook.com/v23.0/1555000111/messages"
    assert reply["headers"]["authorization"] == "Bearer wa-access-token"
    assert reply["json"]["to"] == BUYER_PHONE and reply["json"]["type"] == "text"
    assert reply["json"]["text"]["body"] == "Hello Funke! What are you looking for today?"


def test_the_same_delivery_twice_is_answered_once(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel(say("Hi!")))

    post_webhook(client, whatsapp_payload("Hello", message_id="wamid.same"))
    post_webhook(client, whatsapp_payload("Hello", message_id="wamid.same"))

    assert [text for _, text in messages_in(env)] == ["Hello", "Hi!"]
    assert env.texts_to(BUYER_PHONE) == ["Hi!"]


def test_delivery_receipts_are_ignored(env: Env, client: TestClient) -> None:
    receipt = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.out", "status": "delivered"}]}}]}]}
    use_model(ScriptedModel())

    assert post_webhook(client, receipt).status_code == 200
    with env.session() as session:
        assert session.scalar(select(Conversation)) is None


def test_a_failed_delivery_is_logged_with_metas_reason(
    env: Env, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    failure = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.out",
                                    "status": "failed",
                                    "recipient_id": "2348030000000",
                                    "errors": [{"code": 131047, "title": "Re-engagement message"}],
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    with caplog.at_level(logging.WARNING, logger="app.routes_webhooks"):
        assert post_webhook(client, failure).status_code == 200

    assert "131047: Re-engagement message" in caplog.text
    assert "…0000" in caplog.text


def test_a_later_message_continues_the_same_conversation(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel(say("Hi!"), say("Size 43 is available.")))

    post_webhook(client, whatsapp_payload("Hello", message_id="wamid.1"))
    post_webhook(client, whatsapp_payload("Size 43?", message_id="wamid.2"))

    assert [role for role, _ in messages_in(env)] == [MessageRole.BUYER, MessageRole.AI] * 2
    with env.session() as session:
        assert len(list(session.scalars(select(Conversation)))) == 1


@pytest.mark.parametrize("status", [ConversationStatus.PAUSED, ConversationStatus.NEEDS_ATTENTION])
def test_sowo_stays_quiet_when_ada_has_the_chat(env: Env, client: TestClient, status: ConversationStatus) -> None:
    chat = new_chat(env, simulator=False, name="Funke")
    with env.session() as session:
        conversation = session.get(Conversation, chat)
        assert conversation is not None
        conversation.status = status
        conversation.ai_paused = status == ConversationStatus.PAUSED
        session.commit()
    use_model(ScriptedModel())  # asking the model anything would fail the test

    post_webhook(client, whatsapp_payload("Hello? Anyone there?"))

    assert messages_in(env) == [(MessageRole.BUYER, "Hello? Anyone there?")]
    assert env.texts_to(BUYER_PHONE) == []


def test_pictures_get_a_polite_text_only_reply_without_the_model(env: Env, client: TestClient) -> None:
    payload = whatsapp_payload()
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    message.update({"type": "image", "image": {"id": "media-1"}})
    del message["text"]
    use_model(ScriptedModel())

    post_webhook(client, payload)

    assert messages_in(env) == [(MessageRole.BUYER, "[image message]"), (MessageRole.AI, NON_TEXT_REPLY)]
    assert env.texts_to(BUYER_PHONE) == [NON_TEXT_REPLY]


def test_echo_mode_checks_the_wiring_without_a_model(env: Env, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_ECHO_MODE", "true")
    get_settings.cache_clear()
    use_model(ScriptedModel())

    post_webhook(client, whatsapp_payload("ping"))

    assert env.texts_to(BUYER_PHONE) == ["Echo: ping"]


# -- when things go wrong ------------------------------------------------------------------------------


class BrokenModel:
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        raise OllamaError("Ollama is not running")


def test_if_the_model_is_down_the_buyer_and_ada_are_both_told(env: Env, client: TestClient) -> None:
    use_model(BrokenModel())

    assert post_webhook(client, whatsapp_payload("Hello")).status_code == 200

    assert env.texts_to(BUYER_PHONE) == [TROUBLE_REPLY]
    assert env.conversation().status == ConversationStatus.NEEDS_ATTENTION
    assert env.texts_to(VENDOR_PHONE) == ["Funke needs you: The assistant could not reach its model."]


def test_a_hand_off_by_the_model_alerts_ada(env: Env, client: TestClient) -> None:
    use_model(
        ScriptedModel(
            call("escalate_to_vendor", reason="Wants to exchange size 38 heels"),
            say("Ada will reply you here shortly."),
        )
    )

    post_webhook(client, whatsapp_payload("These heels are too tight, I want to exchange"))

    assert env.texts_to(BUYER_PHONE) == ["Ada will reply you here shortly."]
    assert env.texts_to(VENDOR_PHONE) == ["Funke needs you: Wants to exchange size 38 heels."]
    assert env.conversation().status == ConversationStatus.NEEDS_ATTENTION


def test_a_meta_outage_does_not_lose_the_reply_or_break_the_webhook(env: Env, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        whatsapp, "_transport_override", httpx.MockTransport(lambda _: httpx.Response(503, json={"error": "down"}))
    )
    use_model(ScriptedModel(say("Hi!")))

    assert post_webhook(client, whatsapp_payload("Hello")).status_code == 200
    assert messages_in(env)[-1] == (MessageRole.AI, "Hi!")  # saved, so the dashboard still shows it


def test_nothing_is_sent_when_whatsapp_is_not_configured(env: Env, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "")
    get_settings.cache_clear()
    use_model(ScriptedModel(say("Hi!")))

    post_webhook(client, whatsapp_payload("Hello"))

    assert env.graph == []
    assert messages_in(env)[-1] == (MessageRole.AI, "Hi!")


# -- Ada replying from the dashboard -------------------------------------------------------------------


def test_ada_replies_from_the_dashboard_and_sowo_steps_aside(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel(say("Hi!")))
    post_webhook(client, whatsapp_payload("Hello", message_id="wamid.1"))
    chat = env.conversation().id

    reply = client.post(f"/conversations/{chat}/messages", json={"body": "Hi Funke, Ada here."})
    assert reply.status_code == 200
    assert env.texts_to(BUYER_PHONE)[-1] == "Hi Funke, Ada here."

    post_webhook(client, whatsapp_payload("Thanks Ada", message_id="wamid.2"))
    assert messages_in(env)[-1] == (MessageRole.BUYER, "Thanks Ada")  # no AI reply after it
    assert json.dumps(env.graph).count("Thanks Ada") == 0
