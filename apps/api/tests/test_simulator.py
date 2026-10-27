"""The simulator endpoints behind the web app's /try page: the contract's POST /simulator/*."""

from typing import Any

import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import ScriptedModel, call, say, use_model
from scenarios import loafers_sale_model, new_chat, sell_loafers
from sqlalchemy import select

from app.config import get_settings
from app.models import Order, OrderStatus, Product, StockHold

BUYER_LINES = ("How much for the black loafers, size 43?", "Can you do 35k?", "Make it 41k", "Deliver to Ikeja")


def send(client: TestClient, body: str, conversation_id: str | None = None, **extra: Any) -> dict[str, Any]:
    payload = {"body": body, **extra}
    if conversation_id:
        payload["conversationId"] = conversation_id
    response = client.post("/simulator/messages", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def sell_through_api(client: TestClient) -> tuple[str, str]:
    """Run the sale over HTTP. Returns the conversation id and the order's payment reference."""
    use_model(loafers_sale_model())
    conversation_id: str | None = None
    reply: dict[str, Any] = {}
    for line in BUYER_LINES:
        reply = send(client, line, conversation_id)
        conversation_id = reply["conversation"]["id"]
    reference = reply["messages"][-1]["toolCalls"][-1]["output"]["reference"]
    assert conversation_id
    return conversation_id, reference


def test_the_first_message_starts_a_simulator_conversation(client: TestClient) -> None:
    use_model(ScriptedModel(say("Hello! What are you looking for today?")))

    reply = send(client, "Hello", customerName="Kelechi")

    assert reply["conversation"]["platform"] == "SIMULATOR"
    assert reply["conversation"]["status"] == "AI_ACTIVE"
    assert reply["conversation"]["customerName"] == "Kelechi"
    buyer, ai = reply["messages"]
    assert (buyer["sender"], buyer["body"]) == ("BUYER", "Hello")
    assert (ai["sender"], ai["body"]) == ("AI", "Hello! What are you looking for today?")
    assert "toolCalls" not in buyer  # optional fields are left out, not null
    listed = client.get("/conversations").json()["conversations"]
    assert [c["id"] for c in listed] == [reply["conversation"]["id"]]


def test_the_buyer_is_called_demo_buyer_unless_they_say_otherwise(client: TestClient) -> None:
    use_model(ScriptedModel(say("Hi!")))
    assert send(client, "Hi")["conversation"]["customerName"] == "Demo buyer"


def test_ai_replies_carry_the_tool_calls_the_dashboard_shows(client: TestClient) -> None:
    use_model(
        ScriptedModel(
            call("evaluate_offer", sku="LOAF-BLK-43", offer_naira=35000),
            say("₦35,000 is too low. The best I can do is ₦43,000."),
        )
    )

    reply = send(client, "Can you do 35k?")

    tool_call = reply["messages"][1]["toolCalls"][0]
    assert tool_call["tool"] == "evaluate_offer"
    assert tool_call["input"]["offerKobo"] == 3_500_000
    assert tool_call["output"] == {"decision": "COUNTER", "counterKobo": 4_300_000}
    assert "floor" not in str(reply).lower()


def test_a_follow_up_continues_the_same_conversation(client: TestClient) -> None:
    use_model(ScriptedModel(say("Hi!"), say("Size 43 is available.")))

    first = send(client, "Hello")
    second = send(client, "Size 43?", first["conversation"]["id"])

    assert second["conversation"]["id"] == first["conversation"]["id"]
    history = client.get(f"/conversations/{first['conversation']['id']}/messages").json()["messages"]
    assert [m["sender"] for m in history] == ["BUYER", "AI", "BUYER", "AI"]


def test_when_sowo_hands_over_a_later_message_gets_no_reply(client: TestClient) -> None:
    use_model(ScriptedModel(call("escalate_to_vendor", reason="Wants a refund"), say("Ada will reply you here soon.")))
    first = send(client, "I want a refund")
    assert first["conversation"]["status"] == "NEEDS_ATTENTION"

    use_model(ScriptedModel())  # asking the model anything would fail
    second = send(client, "Hello?", first["conversation"]["id"])

    assert [m["sender"] for m in second["messages"]] == ["BUYER"]


def test_ada_can_pause_a_simulator_chat_from_the_dashboard(client: TestClient) -> None:
    use_model(ScriptedModel(say("Hi!")))
    chat = send(client, "Hello")["conversation"]["id"]
    assert client.post(f"/conversations/{chat}/pause").json()["conversation"]["status"] == "HUMAN_TAKEOVER"

    use_model(ScriptedModel())
    assert [m["sender"] for m in send(client, "Anyone?", chat)["messages"]] == ["BUYER"]

    client.post(f"/conversations/{chat}/resume")
    use_model(ScriptedModel(say("Yes, I'm here!")))
    assert [m["sender"] for m in send(client, "Anyone?", chat)["messages"]] == ["BUYER", "AI"]


@pytest.mark.parametrize("body", ["", "   "])
def test_empty_messages_are_a_bad_request(client: TestClient, body: str) -> None:
    response = client.post("/simulator/messages", json={"body": body})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_an_unknown_conversation_is_not_found(client: TestClient) -> None:
    response = client.post("/simulator/messages", json={"conversationId": "nope", "body": "hi"})
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"


def test_a_real_whatsapp_chat_cannot_be_driven_through_the_simulator(env: Env, client: TestClient) -> None:
    real = new_chat(env, simulator=False, name="Funke")
    response = client.post("/simulator/messages", json={"conversationId": real, "body": "hi"})
    assert response.status_code == 404


def test_the_simulator_can_be_switched_off(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATOR_ENABLED", "false")
    get_settings.cache_clear()
    assert client.post("/simulator/messages", json={"body": "hi"}).status_code == 404
    assert client.post("/simulator/payments", json={"reference": "x", "outcome": "SUCCESS"}).status_code == 404


# -- payments ------------------------------------------------------------------------------------------


def test_a_successful_simulated_payment_pays_the_order_and_sends_a_receipt(env: Env, client: TestClient) -> None:
    chat, reference = sell_through_api(client)

    response = client.post("/simulator/payments", json={"reference": reference, "outcome": "SUCCESS"})

    assert response.status_code == 200
    body = response.json()
    assert body["order"]["paymentStatus"] == "PAID" and body["order"]["fulfillmentStatus"] == "PACKAGING"
    assert body["order"]["totalKobo"] == 4_350_000 and body["order"]["paymentReference"] == reference
    assert body["messages"][0]["sender"] == "AI"
    assert body["messages"][0]["body"].startswith(f"Payment confirmed ✅ We've received ₦43,500 for order {reference}")
    assert client.get("/orders").json()["orders"][0]["paymentStatus"] == "PAID"
    history = client.get(f"/conversations/{chat}/messages").json()["messages"]
    assert history[-1]["body"] == body["messages"][0]["body"]
    with env.session() as session:
        loafers = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        assert loafers is not None and loafers.stock == 2
    assert env.graph == []  # the simulator never texts a real phone, the vendor's included


def test_a_failed_simulated_payment_releases_the_stock(env: Env, client: TestClient) -> None:
    _, reference = sell_through_api(client)

    body = client.post("/simulator/payments", json={"reference": reference, "outcome": "FAILED"}).json()

    assert body["order"]["paymentStatus"] == "FAILED"
    assert "didn't go through" in body["messages"][0]["body"]
    with env.session() as session:
        assert session.scalar(select(StockHold)) is None
        order = session.scalar(select(Order))
        assert order is not None and order.status == OrderStatus.CANCELLED


def test_paying_twice_is_a_conflict(client: TestClient) -> None:
    _, reference = sell_through_api(client)
    client.post("/simulator/payments", json={"reference": reference, "outcome": "SUCCESS"})

    again = client.post("/simulator/payments", json={"reference": reference, "outcome": "SUCCESS"})

    assert again.status_code == 409 and again.json()["error"]["code"] == "CONFLICT"


def test_an_unknown_reference_is_not_found(client: TestClient) -> None:
    response = client.post("/simulator/payments", json={"reference": "SW-NOPE", "outcome": "SUCCESS"})
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"


def test_the_simulator_cannot_mark_a_real_buyers_order_paid(env: Env, client: TestClient) -> None:
    sell_loafers(env, new_chat(env, simulator=False, name="Funke"), deliver=True)
    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None
        reference = order.paystack_reference

    response = client.post("/simulator/payments", json={"reference": reference, "outcome": "SUCCESS"})

    assert response.status_code == 404
    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None and order.status == OrderStatus.PENDING


def test_an_invalid_outcome_is_a_bad_request(client: TestClient) -> None:
    response = client.post("/simulator/payments", json={"reference": "SW-1", "outcome": "MAYBE"})
    assert response.status_code == 400
