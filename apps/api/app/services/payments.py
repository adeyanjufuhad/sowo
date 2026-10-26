"""What happens around an order: releasing held stock, and the messages a payment produces."""

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import Conversation, Order, OrderItem, OrderStatus, Product, StockHold
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


def receipt_text(order: Order, summary: str, *, pidgin: bool) -> str:
    """The buyer's receipt. Written by us, not the model: it states money, so it comes from the order."""
    total = format_naira(order.total_kobo)
    area = order.delivery_area or "you"
    reference = order.paystack_reference or order.id
    if pidgin:
        return (
            f"Payment confirm ✅ We don receive {total} for order {reference}.\n"
            f"Ada don dey pack your {summary}. E go reach {area}. Thank you!"
        )
    return (
        f"Payment confirmed ✅ We've received {total} for order {reference}.\n"
        f"Ada is packing your {summary} now and it will be delivered to {area}. Thank you!"
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
