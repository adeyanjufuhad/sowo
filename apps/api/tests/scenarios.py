"""Reusable chats for the tests: start a buyer, talk to Sowo, run the loafers sale."""

from typing import Any

from conftest import Env
from helpers import BUYER_PHONE, ScriptedModel, Turn, call, last_tool_result, say
from sqlalchemy import select

from app.config import get_settings
from app.models import Conversation, Message, MessageRole, Vendor
from app.services import flow


def new_chat(env: Env, *, simulator: bool = True, phone: str | None = None, name: str = "Tester") -> str:
    with env.session() as session:
        vendor = session.scalar(select(Vendor))
        assert vendor is not None
        conversation = Conversation(
            vendor_id=vendor.id,
            customer_phone=phone or (f"sim-{name.lower()}" if simulator else BUYER_PHONE),
            customer_name=name,
            is_simulator=simulator,
        )
        session.add(conversation)
        session.commit()
        return conversation.id


def say_to_sowo(env: Env, conversation_id: str, text: str, model: Any, *, deliver: bool = False) -> Message | None:
    """The buyer writes; returns Sowo's reply (None if Sowo stayed quiet)."""
    with env.session() as session:
        conversation = session.get(Conversation, conversation_id)
        assert conversation is not None
        flow.add_message(session, conversation, MessageRole.BUYER, text)
        return flow.answer_buyer(session, conversation, model, get_settings(), deliver=deliver)


def loafers_sale_model(*, area: str = "Ikeja", closing: Turn | None = None) -> ScriptedModel:
    """Qwen3 playing the whole sale: search, haggle 35k -> 43k -> 41k, quote, payment link.

    `closing` replaces the last message, for tests where the payment link can't be sent.
    """
    return ScriptedModel(
        call("search_catalog", query="black loafers 43"),
        say("The Black Leather Loafers, size 43 are ₦45,000 and we have 3 pairs."),
        call("evaluate_offer", sku="LOAF-BLK-43", offer_naira=35000),
        say("₦35,000 is too low o. The best I can do is ₦43,000."),
        call("evaluate_offer", sku="LOAF-BLK-43", offer_naira=41000),
        say("Deal! ₦41,000. Where should we deliver?"),
        call("get_quote", items=[{"sku": "LOAF-BLK-43", "quantity": 1}], delivery_area=area),
        lambda messages: call("request_payment", quote_id=last_tool_result(messages, "get_quote")["quote_id"]),
        closing
        or (
            lambda messages: say(
                f"Delivery to {area} is ₦2,500, so your total is ₦43,500. "
                f"Pay here: {last_tool_result(messages, 'request_payment')['payment_link']}"
            )
        ),
    )


def sell_loafers(
    env: Env, conversation_id: str, *, deliver: bool = False, area: str = "Ikeja", closing: Turn | None = None
) -> Message:
    """Run the sale up to the payment link and return Sowo's last message."""
    model = loafers_sale_model(area=area, closing=closing)
    reply: Message | None = None
    for text in (
        "How much for the black loafers, size 43?",
        "Can you do 35k?",
        "Make it 41k",
        f"Deliver to {area}",
    ):
        reply = say_to_sowo(env, conversation_id, text, model, deliver=deliver)
    assert reply is not None and model.turns_left == 0
    return reply
