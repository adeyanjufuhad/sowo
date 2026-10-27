"""Paystack: the payment link, and the signed webhook that is the only thing able to mark an order paid."""

from typing import Any

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import BUYER_PHONE, PAYSTACK_SECRET, VENDOR_PHONE, ScriptedModel, paystack_signed, say
from scenarios import new_chat, sell_loafers
from sqlalchemy import select

from app.config import get_settings
from app.models import (
    ConversationStatus,
    Message,
    MessageRole,
    Order,
    OrderStatus,
    Product,
    StockHold,
)
from app.services import paystack
from app.services.paystack import (
    PaystackError,
    buyer_email,
    initialize_transaction,
    verify_signature,
)


def charge(reference: str, amount: Any = 4_350_000, *, currency: str = "NGN", event: str = "charge.success") -> dict:
    return {"event": event, "data": {"reference": reference, "amount": amount, "currency": currency, "status": "success"}}


def post_charge(client: TestClient, payload: dict, **kwargs: Any) -> httpx.Response:
    raw, headers = paystack_signed(payload, **kwargs)
    return client.post("/webhooks/paystack", content=raw, headers=headers)


def pending_order(env: Env) -> Order:
    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None
        return order


@pytest.fixture
def sale(env: Env) -> str:
    """A WhatsApp buyer who has been sent a payment link; returns the order's Paystack reference."""
    sell_loafers(env, new_chat(env, simulator=False, name="Funke"), deliver=True)
    env.graph.clear()
    reference = pending_order(env).paystack_reference
    assert reference
    return reference


# -- the payment link ----------------------------------------------------------------------------------


def test_signature_check() -> None:
    body = b'{"event":"charge.success"}'
    _, headers = paystack_signed({"event": "charge.success"})
    assert verify_signature(b'{"event": "charge.success"}', headers["X-Paystack-Signature"], PAYSTACK_SECRET)
    assert not verify_signature(body, headers["X-Paystack-Signature"], PAYSTACK_SECRET)  # different bytes
    assert not verify_signature(b"{}", None, PAYSTACK_SECRET)
    assert not verify_signature(b"{}", "abc", "")


def test_the_buyer_placeholder_email_is_built_from_the_phone_number(env: Env) -> None:
    assert buyer_email("+234 801 234 5678") == "2348012345678@customers.sowo.invalid"


def test_a_payment_link_is_created_with_the_server_total(env: Env) -> None:
    url = initialize_transaction(reference="SW-1", amount_kobo=4_350_000, email="a@b.test", metadata={"order_id": "o1"})

    assert url == "https://checkout.paystack.test/SW-1"
    sent = env.paystack_calls[0]
    assert sent["url"] == "https://api.paystack.co/transaction/initialize"
    assert sent["headers"]["authorization"] == f"Bearer {PAYSTACK_SECRET}"
    assert sent["json"] == {
        "email": "a@b.test",
        "amount": 4_350_000,
        "currency": "NGN",
        "reference": "SW-1",
        "metadata": {"order_id": "o1"},
    }


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"status": False, "message": "Invalid key"}),
        httpx.Response(200, json={"status": False, "message": "Duplicate reference"}),
        httpx.Response(200, json={"status": True, "data": {}}),
        httpx.Response(200, text="<html>"),
    ],
)
def test_a_refusal_from_paystack_is_one_error(monkeypatch: pytest.MonkeyPatch, env: Env, response: httpx.Response) -> None:
    monkeypatch.setattr(paystack, "_transport_override", httpx.MockTransport(lambda _: response))
    with pytest.raises(PaystackError):
        initialize_transaction(reference="SW-1", amount_kobo=100, email="a@b.test")


def test_whatsapp_buyers_get_a_real_paystack_link(env: Env) -> None:
    chat = new_chat(env, simulator=False, name="Funke")
    reply = sell_loafers(env, chat, deliver=True)

    order = pending_order(env)
    sent = env.paystack_calls[0]["json"]
    assert sent["amount"] == 4_350_000 == order.total_kobo
    assert sent["reference"] == order.paystack_reference
    assert sent["email"] == f"{BUYER_PHONE}@customers.sowo.invalid"
    assert sent["metadata"]["order_id"] == order.id
    assert f"https://checkout.paystack.test/{order.paystack_reference}" in reply.text
    assert reply.text in env.texts_to(BUYER_PHONE)


def test_if_paystack_is_down_no_order_is_left_holding_stock(env: Env) -> None:
    env.paystack_status = 503
    chat = new_chat(env, simulator=False, name="Funke")
    sell_loafers(env, chat, deliver=True, closing=say("Sorry, Ada will send you the payment details."))

    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None and order.status == OrderStatus.CANCELLED
        assert session.scalar(select(StockHold)) is None
    assert env.conversation().status == ConversationStatus.NEEDS_ATTENTION
    assert env.texts_to(VENDOR_PHONE) == ["Funke needs you: Could not create a Paystack payment link."]


def test_without_a_paystack_key_a_real_buyer_is_never_sent_a_dead_link(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "")
    get_settings.cache_clear()
    chat = new_chat(env, simulator=False, name="Funke")
    sell_loafers(env, chat, deliver=True, closing=say("Sorry, Ada will send you the payment details."))

    assert env.paystack_calls == []
    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None and order.status == OrderStatus.CANCELLED
    assert env.texts_to(VENDOR_PHONE) == ["Funke needs you: Paystack is not configured."]


# -- the webhook ---------------------------------------------------------------------------------------


def test_a_charge_with_a_bad_signature_changes_nothing(env: Env, client: TestClient, sale: str) -> None:
    assert post_charge(client, charge(sale), secret="someone-else").status_code == 403
    assert client.post("/webhooks/paystack", json=charge(sale)).status_code == 403
    assert pending_order(env).status == OrderStatus.PENDING


def test_a_successful_charge_marks_the_order_paid_and_tells_everyone(env: Env, client: TestClient, sale: str) -> None:
    assert post_charge(client, charge(sale)).status_code == 200

    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None and order.status == OrderStatus.PAID
        loafers = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        assert loafers is not None and loafers.stock == 2  # one pair sold
        assert session.scalar(select(StockHold)) is None

    receipt = env.texts_to(BUYER_PHONE)[0]
    assert receipt.startswith(f"Payment confirmed ✅ We've received ₦43,500 for order {sale}.")
    assert "Black Leather Loafers, size 43" in receipt and "Ikeja" in receipt
    alert = env.texts_to(VENDOR_PHONE)[0]
    assert alert.startswith("Pack this order: Black Leather Loafers, size 43.")
    assert "Paid ₦43,500" in alert and "Deliver to Ikeja" in alert and BUYER_PHONE in alert


def test_the_same_charge_delivered_twice_is_applied_once(env: Env, client: TestClient, sale: str) -> None:
    post_charge(client, charge(sale))
    post_charge(client, charge(sale))

    with env.session() as session:
        loafers = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
        assert loafers is not None and loafers.stock == 2  # not 1
        receipts = [m for m in session.scalars(select(Message)) if m.role == MessageRole.AI and "Payment confirmed" in m.text]
        assert len(receipts) == 1
    assert len(env.texts_to(BUYER_PHONE)) == 1 and len(env.texts_to(VENDOR_PHONE)) == 1


def test_a_charge_for_the_wrong_amount_does_not_pay_the_order(env: Env, client: TestClient, sale: str) -> None:
    post_charge(client, charge(sale, amount=10_000))

    assert pending_order(env).status == OrderStatus.PENDING
    assert env.texts_to(BUYER_PHONE) == []  # no receipt
    assert env.conversation().status == ConversationStatus.NEEDS_ATTENTION
    assert env.texts_to(VENDOR_PHONE) == [
        f"Check order {sale} before packing: Paystack reported ₦100, but the order total is ₦43,500."
    ]


@pytest.mark.parametrize(
    "payload",
    [
        charge("SW-DOES-NOT-EXIST"),
        charge("{ref}", currency="USD"),
        charge("{ref}", amount="4350000"),  # a string is not an amount
        charge("{ref}", event="transfer.success"),
        charge("{ref}", event="charge.failed"),
    ],
)
def test_charges_that_dont_qualify_leave_the_order_unpaid(env: Env, client: TestClient, sale: str, payload: dict) -> None:
    payload["data"]["reference"] = payload["data"]["reference"].replace("{ref}", sale)

    assert post_charge(client, payload).status_code == 200  # acknowledged, so Paystack stops retrying
    assert pending_order(env).status == OrderStatus.PENDING
    assert env.texts_to(BUYER_PHONE) == []


def test_a_buyers_own_word_never_marks_an_order_paid(env: Env, client: TestClient, sale: str) -> None:
    from helpers import use_model
    from scenarios import say_to_sowo

    use_model(ScriptedModel())
    model = ScriptedModel(say("Thanks! We'll confirm the moment Paystack reports it."))
    say_to_sowo(env, env.conversation().id, "I don pay, see the transfer screenshot", model)

    assert pending_order(env).status == OrderStatus.PENDING
