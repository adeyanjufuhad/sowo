"""Several vendors on one deployment: each WhatsApp number finds its own vendor, and nothing leaks between shops."""

import re
from typing import Any

from conftest import Env
from fastapi.testclient import TestClient
from helpers import (
    BUYER_PHONE,
    VENDOR_PHONE,
    WHATSAPP_NUMBER_ID,
    ScriptedModel,
    call,
    last_tool_result,
    say,
    signed,
    use_model,
    whatsapp_payload,
)
from scenarios import say_to_sowo
from sqlalchemy import select

from app.models import Conversation, DeliveryZone, Message, Offer, Product, Vendor
from app.services.orders import get_quote
from app.services.vendors import owner_name, vendor_bank

BOLA_NUMBER_ID = "1555000222"
BOLA_ALERT_PHONE = "2348077777777"
ADA_ONLY_SKU = "SNEAK-WHT-41"  # in Ada's catalog, not Bola's


def add_bola(env: Env, **overrides: Any) -> str:
    """A second shop with its own number, alert phone, delivery zone and one product that shares Ada's sku."""
    fields: dict[str, Any] = {
        "name": "Bola's Bags",
        "owner_name": "Bola",
        "whatsapp_phone_number_id": BOLA_NUMBER_ID,
        "alert_phone": BOLA_ALERT_PHONE,
        **overrides,
    }
    with env.session() as session:
        bola = Vendor(**fields)
        session.add(bola)
        session.flush()
        session.add_all(
            [
                Product(
                    vendor_id=bola.id,
                    sku="LOAF-BLK-43",  # the same sku Ada uses for her loafers
                    name="Leather Tote Bag",
                    description="A roomy bag",
                    price_kobo=3_000_000,
                    floor_price_kobo=2_600_000,
                    stock=4,
                ),
                DeliveryZone(vendor_id=bola.id, area="Ibadan", fee_kobo=150_000),
            ]
        )
        session.commit()
        return bola.id


def chat_with(env: Env, vendor_id: str, phone: str = "sim-tester") -> str:
    with env.session() as session:
        conversation = Conversation(vendor_id=vendor_id, customer_phone=phone, customer_name="Tester", is_simulator=True)
        session.add(conversation)
        session.commit()
        return conversation.id


def post_webhook(client: TestClient, payload: dict[str, Any]) -> int:
    raw, headers = signed(payload)
    return client.post("/webhooks/whatsapp", content=raw, headers=headers).status_code


def sent_from(env: Env, number_id: str) -> list[dict[str, Any]]:
    """Every message the Graph API was asked to send from this business number."""
    return [c["json"] for c in env.graph if f"/{number_id}/messages" in c["url"] and c["json"].get("type") == "text"]


# -- finding the vendor ---------------------------------------------------------------------------------


def test_a_message_is_answered_by_the_shop_whose_number_received_it(env: Env, client: TestClient) -> None:
    bola_id = add_bola(env)
    model = ScriptedModel(say("Welcome to Bola's Bags!"))
    use_model(model)

    status = post_webhook(client, whatsapp_payload("hi", phone_number_id=BOLA_NUMBER_ID))

    assert status == 200
    with env.session() as session:
        chat = session.scalar(select(Conversation).where(Conversation.customer_phone == BUYER_PHONE))
        assert chat is not None and chat.vendor_id == bola_id
    # the reply left from Bola's number, and Ada's number sent nothing
    assert [m["text"]["body"] for m in sent_from(env, BOLA_NUMBER_ID)] == ["Welcome to Bola's Bags!"]
    assert sent_from(env, WHATSAPP_NUMBER_ID) == []
    system = model.requests[0]["messages"][0]["content"]
    assert "Bola's Bags" in system and "Ada's Footwear" not in system


def test_the_same_buyer_gets_a_separate_chat_with_each_shop(env: Env, client: TestClient) -> None:
    bola_id = add_bola(env)
    use_model(ScriptedModel(say("Hello from Ada"), say("Hello from Bola")))

    post_webhook(client, whatsapp_payload("hi", message_id="wamid.a"))
    post_webhook(client, whatsapp_payload("hi", message_id="wamid.b", phone_number_id=BOLA_NUMBER_ID))

    with env.session() as session:
        chats = list(session.scalars(select(Conversation).where(Conversation.customer_phone == BUYER_PHONE)))
        assert len(chats) == 2 and {chat.vendor_id for chat in chats} == {bola_id, chats[0].vendor_id}
        assert chats[0].vendor_id != chats[1].vendor_id
        for chat in chats:  # nothing from one shop's chat appears in the other's
            assert len(list(session.scalars(select(Message).where(Message.conversation_id == chat.id)))) == 2


def test_a_message_to_a_number_nobody_connected_is_dropped(env: Env, client: TestClient) -> None:
    model = ScriptedModel()
    use_model(model)

    status = post_webhook(client, whatsapp_payload("hi", phone_number_id="999000999"))

    assert status == 200  # Meta must not retry it
    with env.session() as session:
        assert session.scalar(select(Conversation)) is None
    assert model.requests == [] and env.graph == []


def test_a_message_without_a_number_is_dropped_too(env: Env, client: TestClient) -> None:
    payload = whatsapp_payload("hi")
    del payload["entry"][0]["changes"][0]["value"]["metadata"]
    model = ScriptedModel()
    use_model(model)

    assert post_webhook(client, payload) == 200
    with env.session() as session:
        assert session.scalar(select(Conversation)) is None
    assert model.requests == []


def test_alerts_go_to_the_shops_own_phone_from_the_shops_own_number(env: Env, client: TestClient) -> None:
    add_bola(env)
    use_model(ScriptedModel(call("escalate_to_vendor", reason="wants a refund"), say("Bola will reply soon.")))

    post_webhook(client, whatsapp_payload("I want a refund", phone_number_id=BOLA_NUMBER_ID))

    alerts = [m for m in sent_from(env, BOLA_NUMBER_ID) if m["to"] == BOLA_ALERT_PHONE]
    assert [m["text"]["body"] for m in alerts] == ["Funke needs you: wants a refund."]
    assert env.texts_to(VENDOR_PHONE) == []  # Ada's phone heard nothing about Bola's buyer


def test_a_shop_without_an_alert_phone_just_logs_the_alert(env: Env, client: TestClient) -> None:
    add_bola(env, alert_phone=None)
    use_model(ScriptedModel(call("escalate_to_vendor", reason="wants a refund"), say("Bola will reply soon.")))

    post_webhook(client, whatsapp_payload("refund please", phone_number_id=BOLA_NUMBER_ID))

    assert [m["to"] for m in sent_from(env, BOLA_NUMBER_ID)] == [BUYER_PHONE]


def test_a_shop_with_no_whatsapp_number_cannot_send(env: Env, client: TestClient) -> None:
    """Replies from the dashboard to a shop that never connected a number are saved but not sent."""
    from helpers import sign_in_vendor

    with env.session() as session:
        quiet = Vendor(name="Quiet Shop")
        session.add(quiet)
        session.commit()
        token = sign_in_vendor(session, quiet, email="quiet@example.com")
        chat = Conversation(vendor_id=quiet.id, customer_phone=BUYER_PHONE, customer_name="Funke")
        session.add(chat)
        session.commit()
        chat_id = chat.id

    response = client.post(
        f"/conversations/{chat_id}/messages", json={"body": "Hello!"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert env.graph == []


# -- nothing leaks between shops ------------------------------------------------------------------------


def test_the_assistant_only_sees_its_own_shops_catalog_and_delivery_areas(env: Env) -> None:
    bola_id = add_bola(env)
    chat = chat_with(env, bola_id)
    model = ScriptedModel(
        call("search_catalog", query="sneakers"),
        lambda messages: say("We have: " + str(last_tool_result(messages, "search_catalog")["results"])),
    )

    reply = say_to_sowo(env, chat, "any sneakers?", model)

    assert reply is not None and reply.text == "We have: []"
    system = model.requests[0]["messages"][0]["content"]
    assert "We deliver to: Ibadan." in system
    for ada_only in ("Ikeja", "Lekki", "Yaba", "Sneakers"):
        assert ada_only not in model.everything_sent


def test_a_sku_that_two_shops_share_means_each_shops_own_product(env: Env) -> None:
    bola_id = add_bola(env)
    chat = chat_with(env, bola_id)
    model = ScriptedModel(
        call("get_quote", items=[{"sku": "LOAF-BLK-43", "quantity": 1}], delivery_area="Ibadan"),
        lambda messages: say(f"Total {last_tool_result(messages, 'get_quote')['total']}"),
    )

    reply = say_to_sowo(env, chat, "the tote please, deliver to Ibadan", model)

    assert reply is not None and reply.text == "Total ₦31,500"  # Bola's ₦30,000 + ₦1,500 delivery, not Ada's loafers
    assert "Leather Tote Bag" in model.everything_sent and "Loafers" not in model.everything_sent


def test_another_shops_sku_is_unknown_to_the_assistant(env: Env) -> None:
    chat = chat_with(env, add_bola(env))
    model = ScriptedModel(
        call("evaluate_offer", sku=ADA_ONLY_SKU, offer_naira=20000),
        lambda messages: say(str(last_tool_result(messages, "evaluate_offer"))),
    )

    reply = say_to_sowo(env, chat, "do the white sneakers for 20k", model)

    assert reply is not None and "no product with sku" in reply.text
    with env.session() as session:
        assert session.scalar(select(Offer)) is None  # no offer was recorded


def test_quotes_refuse_another_shops_products_and_zones(env: Env) -> None:
    bola_id = add_bola(env)
    chat = chat_with(env, bola_id)
    with env.session() as session:
        ada_product = session.scalar(select(Product).where(Product.sku == ADA_ONLY_SKU))
        bola_product = session.scalar(select(Product).where(Product.vendor_id == bola_id))
        assert ada_product is not None and bola_product is not None

        stolen = get_quote(session, chat, [{"product_id": ada_product.id, "qty": 1}], "Ibadan")
        assert stolen["error"]["code"] == "NOT_FOUND"
        wrong_zone = get_quote(session, chat, [{"product_id": bola_product.id, "qty": 1}], "Ikeja")
        assert wrong_zone["error"]["code"] == "UNKNOWN_DELIVERY_AREA"
        fine = get_quote(session, chat, [{"product_id": bola_product.id, "qty": 2}], "ibadan")
        assert fine["totalKobo"] == 2 * 3_000_000 + 150_000
        assert get_quote(session, "no-such-chat", [{"product_id": bola_product.id, "qty": 1}], "Ibadan")["error"]["code"] == "NOT_FOUND"


def test_a_conversation_that_is_not_the_buyers_shop_cannot_use_its_ids(env: Env) -> None:
    """A model that learned another shop's product id (it never is shown one) still can't use it."""
    bola_id = add_bola(env)
    chat = chat_with(env, bola_id)
    with env.session() as session:
        ada_product = session.scalar(select(Product).where(Product.sku == ADA_ONLY_SKU))
        assert ada_product is not None
        ada_id = ada_product.id
    model = ScriptedModel(
        call("evaluate_offer", sku=ada_id, offer_naira=1000),
        lambda messages: say(str(last_tool_result(messages, "evaluate_offer"))),
    )

    reply = say_to_sowo(env, chat, "offer", model)

    assert reply is not None and "no product with sku" in reply.text


# -- each shop's own setup ------------------------------------------------------------------------------


def test_each_shop_has_its_own_payment_mode_and_owner(env: Env) -> None:
    env.configure_vendor(
        payment_mode="manual", bank_name="GTBank", bank_account_name="Ada Okafor", bank_account_number="0123456789"
    )
    bola_id = add_bola(env)  # Paystack, the default
    with env.session() as session:
        ada = session.scalar(select(Vendor).where(Vendor.name == "Ada's Footwear"))
        assert ada is not None
        ada_id = ada.id

    ada_model, bola_model = ScriptedModel(say("Hi")), ScriptedModel(say("Hi"))
    say_to_sowo(env, chat_with(env, ada_id, "sim-a"), "hi", ada_model)
    say_to_sowo(env, chat_with(env, bola_id, "sim-b"), "hi", bola_model)

    ada_tools = [t["function"]["name"] for t in ada_model.requests[0]["tools"]]
    bola_tools = [t["function"]["name"] for t in bola_model.requests[0]["tools"]]
    assert "report_payment_sent" in ada_tools and "report_payment_sent" not in bola_tools
    assert "buyers for the owner, Ada." in ada_model.requests[0]["messages"][0]["content"]
    assert "buyers for the owner, Bola." in bola_model.requests[0]["messages"][0]["content"]
    assert "Paystack confirms payment" in bola_model.requests[0]["messages"][0]["content"]


def test_the_owner_name_falls_back_to_the_business_name() -> None:
    assert owner_name(Vendor(name="Bola's Bags", owner_name="Bola")) == "Bola"
    assert owner_name(Vendor(name="Bola's Bags", owner_name=None)) == "Bola's Bags"
    assert owner_name(Vendor(name="Bola's Bags", owner_name="  ")) == "Bola's Bags"


def test_bank_details_must_be_complete_to_count() -> None:
    complete = Vendor(name="x", bank_name="GTBank", bank_account_name="Ada", bank_account_number="0123 456 789")
    assert vendor_bank(complete) == {"bankName": "GTBank", "accountName": "Ada", "accountNumber": "0123456789"}
    for missing in ("bank_name", "bank_account_name", "bank_account_number"):
        incomplete = Vendor(name="x", bank_name="GTBank", bank_account_name="Ada", bank_account_number="0123456789")
        setattr(incomplete, missing, None)
        assert vendor_bank(incomplete) is None
    assert vendor_bank(Vendor(name="x", bank_name="B", bank_account_name="A", bank_account_number="12345")) is None


def test_every_model_message_names_only_its_own_shop(env: Env) -> None:
    bola_id = add_bola(env)
    model = ScriptedModel(say("Hi"))
    say_to_sowo(env, chat_with(env, bola_id), "hi", model)

    assert re.search(r"Ada", model.everything_sent) is None
