"""Scam Shield: real-sounding scams in Pidgin and English are caught, and ordinary buyers are left alone."""

from datetime import timedelta

import pytest
from conftest import Env
from fastapi.testclient import TestClient
from helpers import (
    BUYER_PHONE,
    VENDOR_PHONE,
    ScriptedModel,
    call,
    say,
    sign_in_vendor,
    signed,
    use_model,
    whatsapp_payload,
)
from scenarios import new_chat
from sqlalchemy import select
from test_manual_payments import image_payload, manual_sale, pending_order
from test_simulator import sell_through_api

from app.config import get_settings
from app.models import (
    Conversation,
    ConversationStatus,
    Order,
    OrderStatus,
    ShieldFlag,
    Vendor,
    utc_now,
)
from app.services.flow import safety_reply
from app.services.payments import RECEIPT_RECEIVED_REPLY
from app.services.shield.rules import WARNINGS, asks_for_secrets, claims_payment, scan_text

ALLOWED = ["paystack.com", "paystack.shop"]


def rules_in(text: str) -> list[str]:
    return [finding.rule for finding in scan_text(text, ALLOWED)]


# -- the rules on their own -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("Abeg send me the code wey dem send you", "SECRET_REQUEST"),
        ("Please send me the OTP you just received", "SECRET_REQUEST"),
        ("Give me your BVN make I verify the payment", "SECRET_REQUEST"),
        ("What's your ATM PIN? I need it to refund you", "SECRET_REQUEST"),
        ("Read me the 6 digit code on your phone", "SECRET_REQUEST"),
        ("Oga wetin be your password for the app", "SECRET_REQUEST"),
        ("the OTP that the bank sent, forward it", "SECRET_REQUEST"),
        ("I'm from Paystack, your settlement failed", "IMPERSONATION"),
        ("Good afternoon, I be staff from your bank", "IMPERSONATION"),
        ("This is Paystack support, we need to verify your account", "IMPERSONATION"),
        ("I am calling from GTBank customer care", "IMPERSONATION"),
        ("Hello na WhatsApp security team, your number go block", "IMPERSONATION"),
        ("I be the delivery agent, pay the delivery fee first before I release the package", "IMPERSONATION"),
        ("I'm the dispatch rider, send 3k first make I bring am", "IMPERSONATION"),
        ("Pay through this link bit.ly/sowo-pay", "PHISHING_LINK"),
        ("Click https://paystack-verify.xyz/login to confirm your order", "PHISHING_LINK"),
        ("Use this one instead www.cheap-shoes.shop/pay", "PHISHING_LINK"),
        ("Abeg ship am first, I go pay when e reach", "RELEASE_BEFORE_PAYMENT"),
        ("Send the shoes first then I will transfer", "RELEASE_BEFORE_PAYMENT"),
        ("I'll pay you when I receive it", "RELEASE_BEFORE_PAYMENT"),
        ("Deliver it before I pay, I no dey trust online vendors", "RELEASE_BEFORE_PAYMENT"),
    ],
)
def test_scams_are_caught(text: str, rule: str) -> None:
    assert rule in rules_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "How much for the black loafers?",
        "Abeg do am 35k",
        "Make it 41 na",
        "Na size 43",
        "I dey Ikeja",
        "Send me the account details first",
        "Can you send a picture first?",
        "Send the account number first make I pay",
        "Drop your location pin for delivery",
        "Do you have a promo code? Send me the code for the discount",
        "I am from Lagos, I want two pairs",
        "Is the delivery agent coming today?",
        "Which delivery company una dey use? I go pay now",
        "My number na 08012345678",
        "I paid on https://checkout.paystack.com/abc123",
        "Thank you, God bless you",
        "₦45,000.00 is too much for me",
        "My email is funke@gmail.com",
        "I'll pay now now",
        "Can I pay on delivery?",
        "I'm with my sister, she wants sandals too",
    ],
)
def test_ordinary_buyers_are_left_alone(text: str) -> None:
    assert rules_in(text) == []


@pytest.mark.parametrize(
    "text", ["I don transfer, check am", "I have paid", "Payment done", "Check your account, I don send am", "I just paid"]
)
def test_payment_claims_are_recognised(text: str) -> None:
    assert claims_payment(text)


@pytest.mark.parametrize("text", ["How do I pay?", "I go pay now", "Abeg send your account"])
def test_questions_about_paying_are_not_claims(text: str) -> None:
    assert not claims_payment(text)


def test_more_allowed_domains_can_be_configured() -> None:
    assert scan_text("Pay on https://ada-shoes.ng/checkout", ["ada-shoes.ng"]) == []


# -- in a conversation ------------------------------------------------------------------------------------------


def post_text(client: TestClient, text: str, message_id: str) -> None:
    raw, headers = signed(whatsapp_payload(text, message_id=message_id))
    assert client.post("/webhooks/whatsapp", content=raw, headers=headers).status_code == 200


def flags(env: Env) -> list[ShieldFlag]:
    with env.session() as session:
        return list(session.scalars(select(ShieldFlag).order_by(ShieldFlag.created_at)))


def test_a_pidgin_code_request_hands_the_chat_to_the_vendor(env: Env, client: TestClient) -> None:
    chat = new_chat(env, simulator=False, name="Funke")
    use_model(ScriptedModel())  # the model is never asked

    post_text(client, "Abeg send me the code wey dem send you", "wamid.scam1")

    assert env.conversation().id == chat
    assert env.conversation().status == ConversationStatus.NEEDS_ATTENTION
    assert env.texts_to(BUYER_PHONE) == [safety_reply(pidgin=True, owner="Ada")]
    [alert] = env.texts_to(VENDOR_PHONE)
    assert "Scam Shield" in alert and WARNINGS["SECRET_REQUEST"] in alert
    [flag] = flags(env)
    assert (flag.rule, flag.severity, flag.evidence) == ("SECRET_REQUEST", "high", "send me the code")


def test_once_the_vendor_has_the_chat_more_scam_messages_get_no_reply(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel())

    post_text(client, "I'm from Paystack, your settlement failed", "wamid.scam1")
    post_text(client, "Please send me the OTP now", "wamid.scam2")

    assert env.texts_to(BUYER_PHONE) == [safety_reply(pidgin=False, owner="Ada")]
    assert [flag.rule for flag in flags(env)] == ["IMPERSONATION", "SECRET_REQUEST"]


def test_the_same_rule_is_flagged_once_until_resolved(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel(say("Hi!"), say("Hello again!")))

    post_text(client, "See this bit.ly/abc", "wamid.l1")
    post_text(client, "Or this one tinyurl.com/xyz", "wamid.l2")

    assert [flag.rule for flag in flags(env)] == ["PHISHING_LINK"]


def test_a_strange_link_is_flagged_but_the_sale_carries_on(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel(say("Hi! Which pair caught your eye?")))

    post_text(client, "I saw your shoes on bit.ly/ada-shoes, how much?", "wamid.link")

    assert env.texts_to(BUYER_PHONE) == ["Hi! Which pair caught your eye?"]
    assert env.conversation().status == ConversationStatus.ACTIVE
    [flag] = flags(env)
    assert (flag.rule, flag.severity) == ("PHISHING_LINK", "medium")


def test_a_screenshot_while_a_transfer_is_awaited_warns_the_vendor_and_pays_nothing(
    client: TestClient, manual: Env
) -> None:
    manual_sale(manual)
    raw, headers = signed(image_payload())

    client.post("/webhooks/whatsapp", content=raw, headers=headers)

    assert pending_order(manual).status == OrderStatus.PENDING
    chat = manual.conversation().id
    listing = client.get(f"/conversations/{chat}/messages").json()
    assert [flag["warning"] for flag in listing["flags"]] == ["Unverified screenshot. Check your bank app before you pack."]
    assert listing["conversation"]["openFlags"] == 1
    assert manual.texts_to(BUYER_PHONE)[-1] == RECEIPT_RECEIVED_REPLY  # "the owner will confirm", never "paid"


def test_try_receipt_button_is_flagged_the_same_way(client: TestClient, manual: Env) -> None:
    reference = manual_sale(manual, simulator=True)

    response = client.post("/simulator/receipts", json={"reference": reference})

    assert response.json()["order"]["paymentStatus"] == "PENDING"
    assert [flag.rule for flag in flags(manual)] == ["UNVERIFIED_PAYMENT"]


def test_saying_i_have_paid_with_an_order_waiting_is_flagged(client: TestClient, manual: Env) -> None:
    manual_sale(manual)
    use_model(ScriptedModel(call("report_payment_sent"), say("Thanks! Ada will confirm once the money shows.")))

    post_text(client, "I don transfer, check am", "wamid.paid")

    [flag] = flags(manual)
    assert (flag.rule, flag.evidence) == ("UNVERIFIED_PAYMENT", "I don transfer, check am")
    assert pending_order(manual).status == OrderStatus.PENDING


def test_a_normal_sale_raises_no_flags(env: Env, client: TestClient) -> None:
    sell_through_api(client)
    assert flags(env) == []


def test_repeated_failed_payments_are_flagged(env: Env, client: TestClient) -> None:
    chat = new_chat(env, simulator=False, name="Funke")
    with env.session() as session:
        for status in (OrderStatus.EXPIRED, OrderStatus.CANCELLED):
            session.add(Order(conversation_id=chat, status=status, total_kobo=4_500_000, expires_at=utc_now() - timedelta(hours=1)))
        session.commit()
    use_model(ScriptedModel(say("Do you want to try again?")))

    post_text(client, "Hello, I want the loafers again", "wamid.again")

    assert [flag.rule for flag in flags(env)] == ["REPEATED_FAILED_PAYMENTS"]


def test_try_gets_the_safety_reply_too(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel())

    response = client.post("/simulator/messages", json={"body": "I am calling from GTBank customer care"})

    _buyer, reply = response.json()["messages"]
    assert reply["body"] == safety_reply(pidgin=False, owner="Ada")
    assert response.json()["conversation"]["status"] == "NEEDS_ATTENTION"
    assert response.json()["conversation"]["openFlags"] == 1


# -- the vendor resolves -----------------------------------------------------------------------------------------


def test_the_vendor_resolves_a_flag(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel())
    post_text(client, "Abeg send me the code wey dem send you", "wamid.scam1")
    chat = env.conversation().id
    [flag] = client.get(f"/conversations/{chat}/messages").json()["flags"]
    assert flag["severity"] == "high" and flag["warning"] == WARNINGS["SECRET_REQUEST"]

    response = client.post(f"/conversations/{chat}/flags/{flag['id']}/resolve")

    assert response.status_code == 200 and response.json()["flag"]["resolvedAt"]
    listing = client.get(f"/conversations/{chat}/messages").json()
    assert listing["flags"] == [] and listing["conversation"]["openFlags"] == 0
    assert listing["conversation"]["status"] == "NEEDS_ATTENTION"  # resolving doesn't switch Sowo back on
    assert client.post(f"/conversations/{chat}/flags/{flag['id']}/resolve").status_code == 200  # twice is fine


def test_another_vendor_cannot_resolve_or_see_the_flags(env: Env, client: TestClient) -> None:
    use_model(ScriptedModel())
    post_text(client, "I'm from Paystack, your settlement failed", "wamid.scam1")
    chat = env.conversation().id
    with env.session() as session:
        flag_id = session.scalar(select(ShieldFlag.id))
        bola = Vendor(name="Bola's Bags")
        session.add(bola)
        session.commit()
        token = sign_in_vendor(session, bola, email="bola@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post(f"/conversations/{chat}/flags/{flag_id}/resolve", headers=headers).status_code == 404
    assert client.get(f"/conversations/{chat}/messages", headers=headers).status_code == 404


def test_the_allowed_domains_come_from_settings(env: Env, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHIELD_ALLOWED_DOMAINS", "paystack.com, ada-shoes.ng")
    get_settings.cache_clear()
    use_model(ScriptedModel(say("Yes, that's our site!")))

    post_text(client, "Is ada-shoes.ng/checkout your real site?", "wamid.site")

    assert flags(env) == []
    with env.session() as session:
        assert session.scalar(select(Conversation.status)) == ConversationStatus.ACTIVE


def test_the_shield_never_asks_for_secrets_in_its_own_words() -> None:
    for pidgin in (True, False):
        assert asks_for_secrets(safety_reply(pidgin=pidgin, owner="Ada")) is None
