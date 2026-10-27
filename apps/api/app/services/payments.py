"""What happens around an order: releasing held stock, and the messages a payment produces."""

from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Conversation,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Product,
    StockHold,
    utc_now,
)
from app.services.money import format_naira


def release_order(session: Session, order_id: str, status: OrderStatus = OrderStatus.CANCELLED) -> bool:
    """Give a still-unpaid order's stock back. Returns False if it had already left PENDING."""
    result = session.execute(
        update(Order).where(Order.id == order_id, Order.status == OrderStatus.PENDING).values(status=status)
    )
    if result.rowcount != 1:
        return False
    session.execute(delete(StockHold).where(StockHold.order_id == order_id))
    return True


def order_summary(session: Session, order: Order) -> str:
    """'Black Leather Loafers, size 43' or '2 x Navy Comfort Slides, size 43, Red Block Heels, size 38'."""
    rows = session.execute(
        select(Product.name, OrderItem.quantity)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .where(OrderItem.order_id == order.id)
    )
    parts = [name if quantity == 1 else f"{quantity} x {name}" for name, quantity in rows]
    return "; ".join(parts) or "your order"


def receipt_text(order: Order, summary: str, *, pidgin: bool, owner: str) -> str:
    """The buyer's receipt. Written by us, not the model: it states money, so it comes from the order."""
    total = format_naira(order.total_kobo)
    area = order.delivery_area or "you"
    reference = order.paystack_reference or order.id
    if order.payment_method == PaymentMethod.MANUAL:  # Ada confirmed it herself
        if pidgin:
            return (
                f"Payment confirm ✅ {owner} don see your {total} transfer for order {reference}.\n"
                f"{owner} don dey pack your {summary}. E go reach {area}. Thank you!"
            )
        return (
            f"Payment confirmed ✅ {owner} has confirmed your transfer of {total} for order {reference}.\n"
            f"{owner} is packing your {summary} now and it will be delivered to {area}. Thank you!"
        )
    if pidgin:
        return (
            f"Payment confirm ✅ We don receive {total} for order {reference}.\n"
            f"{owner} don dey pack your {summary}. E go reach {area}. Thank you!"
        )
    return (
        f"Payment confirmed ✅ We've received {total} for order {reference}.\n"
        f"{owner} is packing your {summary} now and it will be delivered to {area}. Thank you!"
    )


def failure_text(*, pidgin: bool) -> str:
    if pidgin:
        return "The payment no go through o. No money comot from your account. You wan try again?"
    return "That payment didn't go through, and nothing was charged. Would you like to try again?"


def pack_alert_text(order: Order, summary: str, conversation: Conversation) -> str:
    """The message that tells the vendor to pack a paid order."""
    reference = order.paystack_reference or order.id
    buyer = conversation.customer_name or conversation.customer_phone
    return (
        f"Pack this order: {summary}.\n"
        f"Paid {format_naira(order.total_kobo)} ({reference}). Deliver to {order.delivery_area or 'the buyer'}.\n"
        f"Buyer: {buyer}, {conversation.customer_phone}."
    )


# -- manual (bank transfer) payments ---------------------------------------------------------------------

RECEIPT_RECEIVED_REPLY = (
    "Thanks! I've sent your receipt to the owner. They'll confirm as soon as the money shows in their account, "
    "and I'll tell you here."
)


def _extend_hold(session: Session, order_id: str, minutes: int) -> None:
    expires = utc_now() + timedelta(minutes=minutes)
    session.execute(update(Order).where(Order.id == order_id).values(expires_at=expires))
    session.execute(update(StockHold).where(StockHold.order_id == order_id).values(expires_at=expires))


def start_manual_payment(session: Session, order_id: str, hold_minutes: int) -> None:
    """Turn a fresh order into a bank-transfer one. People take hours to pay a transfer, so hold the stock longer."""
    session.execute(update(Order).where(Order.id == order_id).values(payment_method=PaymentMethod.MANUAL))
    _extend_hold(session, order_id, hold_minutes)


def open_manual_order(session: Session, conversation_id: str) -> Order | None:
    """The buyer's latest bank-transfer order that is still waiting to be paid."""
    return session.scalar(
        select(Order)
        .where(
            Order.conversation_id == conversation_id,
            Order.payment_method == PaymentMethod.MANUAL,
            Order.status == OrderStatus.PENDING,
        )
        .order_by(Order.created_at.desc())
    )


def report_receipt(session: Session, order: Order, hold_minutes: int) -> bool:
    """The buyer says they've transferred. Returns True the first time, so Ada is only alerted once.

    This never marks anything paid: only Ada does that, after she sees the money in her own account.
    """
    first = order.receipt_reported_at is None
    if first:
        order.receipt_reported_at = utc_now()
    _extend_hold(session, order.id, hold_minutes)  # don't let the stock go back on sale while Ada checks
    return first


def receipt_alert_text(order: Order, conversation: Conversation) -> str:
    reference = order.paystack_reference or order.id
    buyer = conversation.customer_name or conversation.customer_phone
    return (
        f"{buyer} says they've paid {format_naira(order.total_kobo)} for order {reference}.\n"
        f"Check your bank app for the credit (narration {reference}). "
        "If it's there, tap Mark paid in the dashboard."
    )


def revive_expired_order(session: Session, order: Order) -> bool:
    """Ada has the money but the hold lapsed first: take the stock back if it's still there."""
    if order.status != OrderStatus.EXPIRED:
        return False
    now = utc_now()
    items = list(session.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
    for item in items:
        product = session.get(Product, item.product_id)
        held = session.scalar(
            select(func.coalesce(func.sum(StockHold.quantity), 0))
            .join(Order, Order.id == StockHold.order_id)
            .where(
                StockHold.product_id == item.product_id,
                Order.status == OrderStatus.PENDING,
                StockHold.expires_at > now,
            )
        )
        if product is None or product.stock - int(held or 0) < item.quantity:
            return False
    expires = now + timedelta(minutes=5)
    order.status = OrderStatus.PENDING
    order.expires_at = expires
    for item in items:
        session.add(StockHold(product_id=item.product_id, order_id=order.id, quantity=item.quantity, expires_at=expires))
    session.flush()
    return True
