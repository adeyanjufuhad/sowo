"""Bank-transfer mode: Sowo gives Ada's account number, the buyer sends a receipt, Ada taps Mark paid."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import (
    BUYER_PHONE,
    VENDOR_PHONE,
    ScriptedModel,
    call,
    last_tool_result,
    say,
    signed,
    use_model,
    whatsapp_payload,
)
from scenarios import new_chat, say_to_sowo, sell_loafers
from sqlalchemy import select

from app.models import (
    ConversationStatus,
    Message,
    MessageRole,
    Order,
    OrderStatus,
    PaymentMethod,
    Product,
    StockHold,
)
from app.services.flow import NON_TEXT_REPLY_MANUAL
from app.services.payments import RECEIPT_RECEIVED_REPLY, receipt_alert_text

BANK_LINE = "Ada Okafor, GTBank, 0123456789"


def pay_to_ada(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Qwen3 telling the buyer where to pay, copying the account details from the tool result."""
    result = last_tool_result(messages, "request_payment")
    pay_to = result["pay_to"]
    return say(
        f"Your total is ₦43,500. Pay to {pay_to['account_name']}, {pay_to['bank']}, "
        f"{pay_to['account_number']} and use {result['order_reference']} as the narration."
    )


def manual_sale(env: Env, *, simulator: bool = False) -> str:
    """Run the loafers sale in bank-transfer mode. Returns the order's reference."""
    sell_loafers(env, new_chat(env, simulator=simulator, name="Funke"), deliver=not simulator, closing=pay_to_ada)
    return pending_order(env).paystack_reference or ""


def pending_order(env: Env) -> Order:
    with env.session() as session:
        order = session.scalar(select(Order))
        assert order is not None
        return order


def image_payload(message_id: str = "wamid.img1") -> dict[str, Any]:
    payload = whatsapp_payload(message_id=message_id)
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    message.update({"type": "image", "image": {"id": "media-1"}})
    del message["text"]
    return payload


def post_webhook(client: TestClient, payload: dict[str, Any]) -> httpx.Response:
    raw, headers = signed(payload)
    return client.post("/webhooks/whatsapp", content=raw, headers=headers)


# -- giving the buyer Ada's account --------------------------------------------------------------------


def test_the_buyer_is_given_ada_s_account_not_a_payment_link(manual: Env) -> None:
    chat = new_chat(manual, simulator=False, name="Funke")
    reply = sell_loafers(manual, chat, deliver=True, closing=pay_to_ada)

    order = pending_order(manual)
    assert order.payment_method == PaymentMethod.MANUAL and order.status == OrderStatus.PENDING
    assert order.total_kobo == 4_350_000
    assert BANK_LINE in reply.text and order.paystack_reference in reply.text
    assert reply.text in manual.texts_to(BUYER_PHONE)
    assert manual.paystack_calls == []  # Paystack is not involved at all

    output = (reply.tool_calls or [])[-1]["output"]
    assert output["method"] == "MANUAL" and "paymentUrl" not in output
    assert output["bank"] == {"bankName": "GTBank", "accountName": "Ada Okafor", "accountNumber": "0123456789"}
    assert output["amountKobo"] == 4_350_000


def test_stock_is_held_for_hours_not_minutes_while_the_buyer_transfers(manual: Env) -> None:
    manual_sale(manual)

    soon, later = datetime.now(UTC) + timedelta(minutes=170), datetime.now(UTC) + timedelta(minutes=190)
    with manual.session() as session:
        order = session.scalar(select(Order))
        hold = session.scalar(select(StockHold))
        assert order is not None and hold is not None
        for expiry in (order.expires_at, hold.expires_at):
            assert expiry is not None
            assert soon <= expiry.replace(tzinfo=expiry.tzinfo or UTC) <= later


def test_the_prompt_and_tools_follow_the_payment_mode(manual: Env) -> None:
    chat = new_chat(manual)
    model = ScriptedModel(say("Hello!"))
    say_to_sowo(manual, chat, "hi", model)

    tools = [t["function"]["name"] for t in model.requests[0]["tools"]]
    system = model.requests[0]["messages"][0]["content"]
    assert "report_payment_sent" in tools
    assert "Ada confirms payments personally" in system and "Paystack" not in system


def test_in_paystack_mode_there_is_no_manual_tool_or_wording(env: Env) -> None:
    model = ScriptedModel(say("Hello!"))
    say_to_sowo(env, new_chat(env), "hi", model)

    assert "report_payment_sent" not in [t["function"]["name"] for t in model.requests[0]["tools"]]
    assert "Paystack confirms payment" in model.requests[0]["messages"][0]["content"]


@pytest.mark.parametrize("number", ["", "12345", "0123 4567 89 0", "abcdefghij"])
def test_without_valid_bank_details_no_order_is_created(manual: Env, number: str) -> None:
    manual.configure_vendor(bank_account_number=number)
    chat = new_chat(manual, simulator=False, name="Funke")
    sell_loafers(manual, chat, deliver=True, closing=say("Sorry, Ada will send you her account details."))

    with manual.session() as session:
        assert session.scalar(select(Order)) is None
    assert manual.conversation().status == ConversationStatus.NEEDS_ATTENTION
    assert manual.texts_to(VENDOR_PHONE) == ["Funke needs you: Bank transfer details are not set up."]


def test_spaces_in_the_account_number_are_tolerated(manual: Env) -> None:
    manual.configure_vendor(bank_account_number="0123 456 789")
    reply = sell_loafers(manual, new_chat(manual), closing=pay_to_ada)
    assert "0123456789" in reply.text


# -- the buyer says they've paid -----------------------------------------------------------------------


def test_a_receipt_picture_alerts_ada_and_pays_nothing(manual: Env, client: TestClient) -> None:
    reference = manual_sale(manual)
    manual.graph.clear()
    use_model(ScriptedModel())  # a picture never reaches the model

    assert post_webhook(client, image_payload()).status_code == 200

    order = pending_order(manual)
    assert order.status == OrderStatus.PENDING and order.receipt_reported_at is not None
    assert RECEIPT_RECEIVED_REPLY in manual.texts_to(BUYER_PHONE)
    alerts = manual.texts_to(VENDOR_PHONE)
    assert len(alerts) == 1
    assert f"says they've paid ₦43,500 for order {reference}" in alerts[0]
    assert "Mark paid" in alerts[0] and f"narration {reference}" in alerts[0]


def test_sending_the_receipt_twice_alerts_ada_once(manual: Env, client: TestClient) -> None:
    manual_sale(manual)
    manual.graph.clear()
    use_model(ScriptedModel())

    post_webhook(client, image_payload("wamid.img1"))
    post_webhook(client, image_payload("wamid.img2"))

    assert len(manual.texts_to(VENDOR_PHONE)) == 1


def test_a_picture_with_no_transfer_waiting_is_just_a_picture(manual: Env, client: TestClient) -> None:
    use_model(ScriptedModel())
    post_webhook(client, image_payload())

    assert manual.texts_to(BUYER_PHONE) == [NON_TEXT_REPLY_MANUAL]
    assert manual.texts_to(VENDOR_PHONE) == []


def test_a_receipt_still_reaches_ada_when_sowo_is_paused(manual: Env, client: TestClient) -> None:
    manual_sale(manual)
    chat = manual.conversation()
    client.post(f"/conversations/{chat.id}/pause")
    manual.graph.clear()
    use_model(ScriptedModel())

    post_webhook(client, image_payload())

    assert pending_order(manual).receipt_reported_at is not None
    assert len(manual.texts_to(VENDOR_PHONE)) == 1
    assert manual.texts_to(BUYER_PHONE) == []  # Ada has the chat, so Sowo says nothing


def test_i_have_paid_in_words_goes_through_the_model_but_pays_nothing(manual: Env) -> None:
    manual_sale(manual)
    chat = manual.conversation().id
    manual.graph.clear()
    model = ScriptedModel(
        call("report_payment_sent"),
        say("Thanks! I've told Ada and she'll confirm once she sees the money."),
    )

    reply = say_to_sowo(manual, chat, "I don send the money o", model, deliver=True)

    assert reply is not None and "Ada" in reply.text
    order = pending_order(manual)
    assert order.status == OrderStatus.PENDING and order.receipt_reported_at is not None
    assert len(manual.texts_to(VENDOR_PHONE)) == 1


def test_reporting_a_payment_with_nothing_to_pay_is_an_error(manual: Env) -> None:
    chat = new_chat(manual)
    model = ScriptedModel(call("report_payment_sent"), say("There's no open order yet."))
    say_to_sowo(manual, chat, "I paid", model)

    results = [m["content"] for m in model.requests[-1]["messages"] if m["role"] == "tool"]
    assert "no bank-transfer order waiting" in results[0]


def test_the_model_still_cannot_announce_a_payment(manual: Env) -> None:
    manual_sale(manual)
    chat = manual.conversation().id
    model = ScriptedModel(
        say("Payment confirmed, your order is on its way!"),
        say("Thanks, Ada will confirm once she sees the money."),
    )
    reply = say_to_sowo(manual, chat, "I have paid", model)

    assert reply is not None and reply.text == "Thanks, Ada will confirm once she sees the money."


def test_the_receipt_keeps_the_stock_held_while_ada_checks(manual: Env, client: TestClient) -> None:
    manual_sale(manual)
    use_model(ScriptedModel())
    with manual.session() as session:
        hold = session.scalar(select(StockHold))
        assert hold is not None
        hold.expires_at = datetime.now(UTC) + timedelta(minutes=2)  # about to lapse
        session.commit()

    post_webhook(client, image_payload())

    with manual.session() as session:
        hold = session.scalar(select(StockHold))
        assert hold is not None and hold.expires_at is not None
        assert hold.expires_at.replace(tzinfo=hold.expires_at.tzinfo or UTC) > datetime.now(UTC) + timedelta(minutes=170)


# -- Ada taps Mark paid --------------------------------------------------------------------------------


def test_mark_paid_pays_the_order_and_tells_the_buyer(manual: Env, client: TestClient) -> None:
    reference = manual_sale(manual)
    manual.graph.clear()
    order = pending_order(manual)

    response = client.post(f"/orders/{order.id}/mark-paid")

    assert response.status_code == 200
    body = response.json()
    assert body["order"]["paymentStatus"] == "PAID" and body["order"]["fulfillmentStatus"] == "PACKAGING"
    assert body["order"]["paymentMethod"] == "MANUAL" and body["order"]["totalKobo"] == 4_350_000
    receipt = manual.texts_to(BUYER_PHONE)[0]
    assert receipt == body["message"]["body"]
    assert receipt.startswith(f"Payment confirmed ✅ Ada has confirmed your transfer of ₦43,500 for order {reference}.")
    assert "Black Leather Loafers, size 43" in receipt and "Ikeja" in receipt
    assert manual.texts_to(VENDOR_PHONE) == []  # Ada just did it herself; no "pack this" ping
    with manual.session() as session:
        assert session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43")).stock == 2  # type: ignore[union-attr]
        assert session.scalar(select(StockHold)) is None


def test_tapping_mark_paid_twice_does_not_double_anything(manual: Env, client: TestClient) -> None:
    manual_sale(manual)
    order = pending_order(manual)
    manual.graph.clear()

    first = client.post(f"/orders/{order.id}/mark-paid")
    second = client.post(f"/orders/{order.id}/mark-paid")

    assert first.status_code == second.status_code == 200
    assert "message" in first.json() and "message" not in second.json()
    assert len(manual.texts_to(BUYER_PHONE)) == 1
    with manual.session() as session:
        assert session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43")).stock == 2  # type: ignore[union-attr]


def test_the_whole_flow_receipt_then_mark_paid(manual: Env, client: TestClient) -> None:
    manual_sale(manual)
    use_model(ScriptedModel())
    post_webhook(client, image_payload())
    manual.graph.clear()

    client.post(f"/orders/{pending_order(manual).id}/mark-paid")

    orders = client.get("/orders").json()["orders"]
    assert orders[0]["paymentStatus"] == "PAID" and orders[0]["receiptReportedAt"]
    assert manual.conversation().status == ConversationStatus.ACTIVE  # Sowo carries on after the sale


def test_mark_paid_is_refused_for_a_paystack_order(env: Env, client: TestClient) -> None:
    sell_loafers(env, new_chat(env, simulator=False, name="Funke"), deliver=True)
    order = pending_order(env)
    assert order.payment_method == PaymentMethod.PAYSTACK

    response = client.post(f"/orders/{order.id}/mark-paid")

    assert response.status_code == 409 and "Paystack" in response.json()["error"]["message"]
    assert pending_order(env).status == OrderStatus.PENDING  # Ada cannot override Paystack's verification


def test_mark_paid_on_an_unknown_order_is_not_found(client: TestClient) -> None:
    response = client.post("/orders/nope/mark-paid")
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"


def test_a_cancelled_order_cannot_be_marked_paid(manual: Env, client: TestClient) -> None:
    manual_sale(manual)
    order = pending_order(manual)
    with manual.session() as session:
        session.query(Order).update({"status": OrderStatus.CANCELLED})
        session.commit()

    assert client.post(f"/orders/{order.id}/mark-paid").status_code == 409


def test_money_that_arrives_after_the_hold_lapsed_can_still_be_confirmed(manual: Env, client: TestClient) -> None:
    manual_sale(manual)
    order = pending_order(manual)
    with manual.session() as session:  # the hold ran out before Ada looked at her bank app
        session.query(Order).update({"status": OrderStatus.EXPIRED})
        session.query(StockHold).delete()
        session.commit()

    response = client.post(f"/orders/{order.id}/mark-paid")

    assert response.status_code == 200 and response.json()["order"]["paymentStatus"] == "PAID"
    with manual.session() as session:
        assert session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43")).stock == 2  # type: ignore[union-attr]


def test_but_not_if_the_stock_has_gone(manual: Env, client: TestClient) -> None:
    manual_sale(manual)
    order = pending_order(manual)
    with manual.session() as session:
        session.query(Order).update({"status": OrderStatus.EXPIRED})
        session.query(StockHold).delete()
        session.query(Product).filter(Product.sku == "LOAF-BLK-43").update({"stock": 0})
        session.commit()

    response = client.post(f"/orders/{order.id}/mark-paid")

    assert response.status_code == 409 and "sold or released" in response.json()["error"]["message"]
    with manual.session() as session:
        assert session.scalar(select(Order)).status == OrderStatus.EXPIRED  # type: ignore[union-attr]


def test_paystack_cannot_pay_a_bank_transfer_order_by_accident(manual: Env, client: TestClient) -> None:
    """A stray charge.success for a bank-transfer reference still needs the exact amount, like any payment."""
    from helpers import paystack_signed

    reference = manual_sale(manual)
    raw, headers = paystack_signed(
        {"event": "charge.success", "data": {"reference": reference, "amount": 100, "currency": "NGN"}}
    )
    client.post("/webhooks/paystack", content=raw, headers=headers)
    assert pending_order(manual).status == OrderStatus.PENDING


# -- the simulator (the /try page) ---------------------------------------------------------------------


def test_the_simulator_buyer_can_send_a_receipt(manual: Env, client: TestClient) -> None:
    reference = manual_sale(manual, simulator=True)

    response = client.post("/simulator/receipts", json={"reference": reference})

    assert response.status_code == 200
    body = response.json()
    assert body["order"]["receiptReportedAt"] and body["order"]["paymentStatus"] == "PENDING"
    assert [m["sender"] for m in body["messages"]] == ["BUYER", "AI"]
    assert body["messages"][1]["body"] == RECEIPT_RECEIVED_REPLY
    assert manual.graph == []  # a simulator chat never texts anyone


def test_simulated_payment_cannot_skip_the_vendor(manual: Env, client: TestClient) -> None:
    reference = manual_sale(manual, simulator=True)

    response = client.post("/simulator/payments", json={"reference": reference, "outcome": "SUCCESS"})

    assert response.status_code == 409 and "vendor" in response.json()["error"]["message"]
    assert pending_order(manual).status == OrderStatus.PENDING


def test_the_receipt_endpoint_refuses_unknown_and_real_buyers_orders(manual: Env, client: TestClient) -> None:
    assert client.post("/simulator/receipts", json={"reference": "SW-NOPE"}).status_code == 404

    real = manual_sale(manual)  # a real WhatsApp buyer's order
    assert client.post("/simulator/receipts", json={"reference": real}).status_code == 404


def test_the_receipt_endpoint_refuses_orders_that_are_not_waiting_for_a_transfer(
    manual: Env, client: TestClient
) -> None:
    reference = manual_sale(manual, simulator=True)
    with manual.session() as session:
        session.query(Order).update({"payment_method": PaymentMethod.PAYSTACK})
        session.commit()
    assert client.post("/simulator/receipts", json={"reference": reference}).status_code == 409

    with manual.session() as session:
        session.query(Order).update({"payment_method": PaymentMethod.MANUAL, "status": OrderStatus.PAID})
        session.commit()
    assert client.post("/simulator/receipts", json={"reference": reference}).status_code == 409


def test_a_simulator_sale_end_to_end_through_the_api(manual: Env, client: TestClient) -> None:
    reference = manual_sale(manual, simulator=True)
    order = pending_order(manual)

    client.post("/simulator/receipts", json={"reference": reference})
    paid = client.post(f"/orders/{order.id}/mark-paid").json()

    assert paid["order"]["paymentStatus"] == "PAID"
    history = client.get(f"/conversations/{order.conversation_id}/messages").json()["messages"]
    assert history[-1]["body"] == paid["message"]["body"]
    assert history[-1]["body"].startswith("Payment confirmed")
    assert manual.graph == []


def test_orders_report_how_they_are_paid(manual: Env, client: TestClient) -> None:
    manual_sale(manual)

    order = client.get("/orders").json()["orders"][0]

    assert order["paymentMethod"] == "MANUAL" and "receiptReportedAt" not in order


def test_the_alert_text_names_the_buyer_amount_and_reference(manual: Env) -> None:
    manual_sale(manual)
    with manual.session() as session:
        order = session.scalar(select(Order))
        chat = manual.conversation()
        assert order is not None
        text = receipt_alert_text(order, chat)
    assert text.startswith("Funke says they've paid ₦43,500 for order SW-")
    assert text.endswith("tap Mark paid in the dashboard.")


def test_no_stray_messages_are_left_behind(manual: Env) -> None:
    """The sale produces exactly the buyer's four messages and Sowo's four replies, nothing else."""
    manual_sale(manual)
    with manual.session() as session:
        roles = [m.role for m in session.scalars(select(Message).order_by(Message.created_at))]
    assert roles == [MessageRole.BUYER, MessageRole.AI] * 4
