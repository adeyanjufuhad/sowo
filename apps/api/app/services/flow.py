"""Conversations end to end.

A buyer message comes in -> Sowo (maybe) answers. A payment comes in -> a receipt goes to the buyer and a
"pack this" alert goes to the vendor. Used by the WhatsApp webhook, the Paystack webhook and the simulator.
"""

import logging
import threading
import time
from datetime import UTC, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.db as database
from app.config import Settings, get_settings
from app.models import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    Order,
    PaymentMethod,
    Vendor,
    utc_now,
)
from app.services import guard, payments, whatsapp
from app.services.agent import AgentReply, run_agent
from app.services.money import format_naira
from app.services.ollama import ChatModel, OllamaError
from app.services.orders import mark_order_paid
from app.services.vendors import owner_name, vendor_for_number
from app.services.whatsapp import InboundMessage

logger = logging.getLogger(__name__)

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

RECEIPT_KINDS = {"image", "document"}
TROUBLE_REPLY = "Sorry, something went wrong on my side. I've told the owner and they'll reply you here shortly."
NON_TEXT_REPLY = (
    "I can only read text messages for now, so please type what you need. "
    "There's no need to send payment screenshots: we confirm payments through Paystack."
)
NON_TEXT_REPLY_MANUAL = "I can only read text messages for now, so please type what you need."


def conversation_lock(conversation_id: str) -> threading.Lock:
    """One lock per chat, so two quick messages from a buyer are answered one after the other."""
    with _locks_guard:
        return _locks.setdefault(conversation_id, threading.Lock())


# -- conversations and messages -------------------------------------------------------------------------


def get_or_create_conversation(session: Session, vendor: Vendor, phone: str, name: str) -> Conversation:
    conversation = session.scalar(
        select(Conversation)
        .where(
            Conversation.vendor_id == vendor.id,
            Conversation.customer_phone == phone,
            Conversation.is_simulator.is_(False),
        )
        .order_by(Conversation.created_at.desc())
    )
    if conversation is None:
        conversation = Conversation(vendor_id=vendor.id, customer_phone=phone, customer_name=name, is_simulator=False)
        session.add(conversation)
    elif name and not conversation.customer_name:
        conversation.customer_name = name
    session.commit()
    return conversation


def add_message(
    session: Session,
    conversation: Conversation,
    role: MessageRole,
    text: str,
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    whatsapp_message_id: str | None = None,
) -> Message:
    """Save a message, stamped no earlier than the chat's latest one so the order never flips."""
    created_at = utc_now()
    latest = session.scalar(select(func.max(Message.created_at)).where(Message.conversation_id == conversation.id))
    if latest is not None:
        latest = latest if latest.tzinfo else latest.replace(tzinfo=UTC)
        created_at = max(created_at, latest + timedelta(milliseconds=1))
    message = Message(
        conversation_id=conversation.id,
        role=role,
        text=text,
        tool_calls=tool_calls or None,
        whatsapp_message_id=whatsapp_message_id,
        created_at=created_at,
    )
    session.add(message)
    session.commit()
    return message


def should_reply(conversation: Conversation) -> bool:
    """Sowo only talks while it is on: not paused by Ada, and not waiting for her after a hand-off."""
    return conversation.status == ConversationStatus.ACTIVE and not conversation.ai_paused


def vendor_of(session: Session, conversation: Conversation) -> Vendor:
    vendor = session.get(Vendor, conversation.vendor_id)
    assert vendor is not None  # conversations.vendor_id is a NOT NULL foreign key
    return vendor


def send_to_buyer(vendor: Vendor, conversation: Conversation, text: str) -> bool:
    """A WhatsApp message to the buyer, sent from the number the vendor's customers know."""
    return whatsapp.send_whatsapp_text(vendor.whatsapp_phone_number_id, conversation.customer_phone, text)


def notify_vendor(vendor: Vendor, text: str) -> None:
    """An alert to the vendor's own phone, sent from their business number."""
    if vendor.alert_phone:
        whatsapp.send_whatsapp_text(vendor.whatsapp_phone_number_id, vendor.alert_phone, text)
    else:
        logger.info("Vendor alert for %s (no alert phone set): %s", vendor.id, text.splitlines()[0])


def _buyer_name(conversation: Conversation) -> str:
    return conversation.customer_name or conversation.customer_phone


def _is_pidgin(session: Session, conversation: Conversation) -> bool:
    recent = session.scalars(
        select(Message.text)
        .where(Message.conversation_id == conversation.id, Message.role == MessageRole.BUYER)
        .order_by(Message.created_at.desc())
        .limit(3)
    )
    return any(guard.looks_like_pidgin(text) for text in recent)


# -- a buyer writes -------------------------------------------------------------------------------------


def answer_buyer(
    session: Session, conversation: Conversation, model: ChatModel, settings: Settings, *, deliver: bool
) -> Message | None:
    """Run the agent on the buyer's latest message and save (and, for WhatsApp, send) its reply."""
    with conversation_lock(conversation.id):
        session.refresh(conversation)  # the vendor may have paused the chat while the buyer was typing
        if not should_reply(conversation):
            return None
        try:
            reply = run_agent(session, conversation, model, settings)
        except OllamaError:
            logger.exception("The model could not be reached")
            reply = AgentReply(text=TROUBLE_REPLY, escalation="The assistant could not reach its model")
        message = add_message(
            session, conversation, MessageRole.AI, reply.text, tool_calls=reply.tool_calls or None
        )
        conversation.greeted = True
        if reply.escalation:
            conversation.status = ConversationStatus.NEEDS_ATTENTION
        session.commit()

    if deliver:
        if settings.reply_delay_seconds:
            time.sleep(settings.reply_delay_seconds)  # a beat of typing, so it doesn't feel like a machine
        vendor = vendor_of(session, conversation)
        send_to_buyer(vendor, conversation, message.text)
        if reply.escalation:
            notify_vendor(vendor, f"{_buyer_name(conversation)} needs you: {reply.escalation}.")
        if reply.receipt_order_id:  # the model passed on "I've paid": tell the vendor to check their account
            order = session.get(Order, reply.receipt_order_id)
            if order is not None:
                notify_vendor(vendor, payments.receipt_alert_text(order, conversation))
    return message


def register_receipt(session: Session, conversation: Conversation, order: Order, settings: Settings) -> bool:
    """The buyer sent a receipt for a bank-transfer order. Flag it and, the first time, alert the vendor.

    Nothing is marked paid here. Only the vendor can do that, once they see the money in their own account.
    """
    first = payments.report_receipt(session, order, settings.manual_payment_hold_minutes)
    session.commit()
    if first and not conversation.is_simulator:
        notify_vendor(vendor_of(session, conversation), payments.receipt_alert_text(order, conversation))
    return first


def submit_simulated_receipt(
    session: Session, conversation: Conversation, order: Order, settings: Settings
) -> list[Message]:
    """The /try page's 'I've sent the transfer' button: the same thing a receipt picture does on WhatsApp."""
    messages = [add_message(session, conversation, MessageRole.BUYER, "I've sent the transfer. Here is my receipt.")]
    register_receipt(session, conversation, order, settings)
    if should_reply(conversation):
        messages.append(add_message(session, conversation, MessageRole.AI, payments.RECEIPT_RECEIVED_REPLY))
    return messages


def handle_inbound(session: Session, inbound: InboundMessage, model: ChatModel, settings: Settings) -> None:
    """One WhatsApp message from a buyer."""
    vendor = vendor_for_number(session, inbound.phone_number_id)
    if vendor is None:
        # Not one of ours (a number nobody connected, or a test message from Meta's dashboard): do not guess a vendor.
        logger.warning("Dropping a WhatsApp message sent to the unknown business number %r", inbound.phone_number_id)
        return
    conversation = get_or_create_conversation(session, vendor, inbound.phone, inbound.name)
    text = inbound.text if inbound.kind == "text" else f"[{inbound.kind} message]"
    try:
        add_message(session, conversation, MessageRole.BUYER, text, whatsapp_message_id=inbound.id)
    except IntegrityError:
        session.rollback()
        logger.info("Ignoring a message WhatsApp delivered twice")
        return
    whatsapp.mark_read(vendor.whatsapp_phone_number_id, inbound.id)

    if inbound.kind != "text":
        # A picture or document while a bank transfer is waiting is the buyer's receipt.
        order = payments.open_manual_order(session, conversation.id) if inbound.kind in RECEIPT_KINDS else None
        if order is not None:
            register_receipt(session, conversation, order, settings)
        if should_reply(conversation):
            if order is not None:
                reply_text = payments.RECEIPT_RECEIVED_REPLY
            elif vendor.payment_mode == "manual":
                reply_text = NON_TEXT_REPLY_MANUAL
            else:
                reply_text = NON_TEXT_REPLY
            reply = add_message(session, conversation, MessageRole.AI, reply_text)
            send_to_buyer(vendor, conversation, reply.text)
        return
    if settings.whatsapp_echo_mode:  # for checking the webhook wiring without a model
        if should_reply(conversation):
            reply = add_message(session, conversation, MessageRole.AI, f"Echo: {inbound.text}")
            send_to_buyer(vendor, conversation, reply.text)
        return
    answer_buyer(session, conversation, model, settings, deliver=True)


def process_inbound(messages: list[InboundMessage], model: ChatModel) -> None:
    """Background job for a webhook delivery. One bad message must not stop the rest."""
    settings = get_settings()
    for inbound in messages:
        try:
            with database.SessionLocal() as session:
                handle_inbound(session, inbound, model, settings)
        except Exception:
            logger.exception("Failed to handle a WhatsApp message")


# -- a payment arrives ------------------------------------------------------------------------------------


def finish_paid_order(session: Session, order_id: str) -> Message | None:
    """After an order is marked paid: receipt to the buyer, 'pack this' to the vendor."""
    order = session.get(Order, order_id)
    if order is None:
        return None
    conversation = session.get(Conversation, order.conversation_id)
    if conversation is None:
        return None
    vendor = vendor_of(session, conversation)
    summary = payments.order_summary(session, order)
    receipt = add_message(
        session,
        conversation,
        MessageRole.AI,
        payments.receipt_text(order, summary, pidgin=_is_pidgin(session, conversation), owner=owner_name(vendor)),
    )
    if not conversation.is_simulator:
        send_to_buyer(vendor, conversation, receipt.text)
        if order.payment_method != PaymentMethod.MANUAL:  # for a bank transfer the vendor just tapped Mark paid
            notify_vendor(vendor, payments.pack_alert_text(order, summary, conversation))
    return receipt


def finish_failed_order(session: Session, order_id: str) -> Message | None:
    """After a payment fails: stock goes back on the shelf and the buyer is told."""
    order = session.get(Order, order_id)
    conversation = session.get(Conversation, order.conversation_id) if order else None
    if order is None or conversation is None:
        return None
    message = add_message(
        session,
        conversation,
        MessageRole.AI,
        payments.failure_text(pidgin=_is_pidgin(session, conversation)),
    )
    if not conversation.is_simulator:
        send_to_buyer(vendor_of(session, conversation), conversation, message.text)
    return message


def process_charge_success(data: dict[str, Any]) -> None:
    """Paystack says a charge succeeded. Mark the order paid only if the reference and amount both match."""
    reference, amount = data.get("reference"), data.get("amount")
    if not isinstance(reference, str) or data.get("currency") != "NGN":
        logger.warning("Ignoring a Paystack charge with no usable reference or a non-NGN currency")
        return
    try:
        with database.SessionLocal() as session:
            result = mark_order_paid(session, reference, amount)  # type: ignore[arg-type]
            session.commit()
            error = result.get("error")
            if error:
                logger.warning("Paystack charge %s not applied: %s", reference, error["code"])
                if error["code"] == "AMOUNT_MISMATCH":
                    _flag_amount_mismatch(session, reference, amount)
                return
            if result.get("paid"):
                finish_paid_order(session, result["orderId"])
    except Exception:
        logger.exception("Failed to process a Paystack charge")


def _flag_amount_mismatch(session: Session, reference: str, amount: object) -> None:
    """A payment that doesn't match its order is suspicious: don't pack, and tell the vendor."""
    order = session.scalar(select(Order).where(Order.paystack_reference == reference))
    if order is None:
        return
    conversation = session.get(Conversation, order.conversation_id)
    if conversation is None:
        return
    conversation.status = ConversationStatus.NEEDS_ATTENTION
    session.commit()
    paid = format_naira(amount) if isinstance(amount, int) and not isinstance(amount, bool) else "an unexpected amount"
    notify_vendor(
        vendor_of(session, conversation),
        f"Check order {reference} before packing: Paystack reported {paid}, "
        f"but the order total is {format_naira(order.total_kobo)}."
    )
