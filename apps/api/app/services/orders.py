from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Conversation,
    DeliveryZone,
    Offer,
    OfferDecision,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    StockHold,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _error(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _normalise_items(items: list[dict[str, Any]]) -> list[tuple[str, int]] | dict[str, Any]:
    quantities: dict[str, int] = {}
    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("qty")
        if not isinstance(product_id, str) or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            return _error("BAD_REQUEST", "Each item needs a product_id and a positive integer qty")
        quantities[product_id] = quantities.get(product_id, 0) + quantity
    if not quantities:
        return _error("BAD_REQUEST", "At least one item is required")
    return list(quantities.items())


def _active_hold_quantities(session: Session, product_ids: list[str], now: datetime) -> dict[str, int]:
    rows = session.execute(
        select(StockHold.product_id, func.coalesce(func.sum(StockHold.quantity), 0))
        .join(Order, Order.id == StockHold.order_id)
        .where(
            StockHold.product_id.in_(product_ids),
            Order.status == OrderStatus.PENDING,
            StockHold.expires_at > now,
        )
        .group_by(StockHold.product_id)
    )
    return {product_id: int(quantity) for product_id, quantity in rows}


def _quote(session: Session, conversation_id: str, items: list[dict[str, Any]], delivery_area: str) -> dict[str, Any]:
    normalised = _normalise_items(items)
    if isinstance(normalised, dict):
        return normalised
    # A chat only ever sees its own vendor's delivery zones and products, whatever ids the caller passes.
    vendor_id = session.scalar(select(Conversation.vendor_id).where(Conversation.id == conversation_id))
    if vendor_id is None:
        return _error("NOT_FOUND", "Conversation not found")
    zone = session.scalar(
        select(DeliveryZone).where(
            DeliveryZone.vendor_id == vendor_id, func.lower(DeliveryZone.area) == delivery_area.casefold()
        )
    )
    if zone is None:
        return _error("UNKNOWN_DELIVERY_AREA", f"Delivery is not available in {delivery_area}")

    product_ids = [product_id for product_id, _ in normalised]
    products = {
        product.id: product
        for product in session.scalars(select(Product).where(
                Product.id.in_(product_ids), Product.vendor_id == vendor_id, Product.archived_at.is_(None)
            )
        )
    }
    if len(products) != len(product_ids):
        return _error("NOT_FOUND", "One or more products could not be found")

    lines: list[dict[str, int | str]] = []
    subtotal_kobo = 0
    for product_id, quantity in normalised:
        product = products[product_id]
        accepted_offer = session.scalar(
            select(Offer)
            .where(
                Offer.conversation_id == conversation_id,
                Offer.product_id == product.id,
                Offer.decision == OfferDecision.ACCEPT,
            )
            .order_by(Offer.created_at.desc())
        )
        unit_price_kobo = (
            min(accepted_offer.amount_kobo, product.price_kobo)
            if accepted_offer is not None
            else product.price_kobo
        )
        line_total_kobo = unit_price_kobo * quantity
        subtotal_kobo += line_total_kobo
        lines.append(
            {
                "productId": product.id,
                "name": product.name,
                "quantity": quantity,
                "unitPriceKobo": unit_price_kobo,
                "lineTotalKobo": line_total_kobo,
            }
        )
    return {
        "lines": lines,
        "subtotalKobo": subtotal_kobo,
        "deliveryArea": zone.area,
        "deliveryFeeKobo": zone.fee_kobo,
        "totalKobo": subtotal_kobo + zone.fee_kobo,
    }


def get_quote(
    session: Session, conversation_id: str, items: list[dict[str, Any]], delivery_area: str
) -> dict[str, Any]:
    """Calculate a quote from database-owned prices and delivery settings only."""
    return _quote(session, conversation_id, items, delivery_area)


def expire_holds(session: Session, now: datetime | None = None) -> int:
    """Expire overdue unpaid orders and delete their holds, returning the order count."""
    now = now or _now()
    expired_order_ids = list(
        session.scalars(
            select(Order.id).where(Order.status == OrderStatus.PENDING, Order.expires_at <= now)
        )
    )
    if not expired_order_ids:
        return 0
    session.execute(
        update(Order)
        .where(Order.id.in_(expired_order_ids), Order.status == OrderStatus.PENDING)
        .values(status=OrderStatus.EXPIRED)
    )
    session.execute(delete(StockHold).where(StockHold.order_id.in_(expired_order_ids)))
    return len(expired_order_ids)


def create_order_with_hold(
    session: Session,
    conversation_id: str,
    items: list[dict[str, Any]],
    delivery_area: str,
) -> dict[str, Any]:
    """Atomically reserve stock for a pending order using server-calculated quote data."""
    now = _now()
    transaction = session.begin_nested() if session.in_transaction() else session.begin()
    with transaction:
        expire_holds(session, now)
        quote = _quote(session, conversation_id, items, delivery_area)
        if "error" in quote:
            return quote
        normalised = _normalise_items(items)
        if isinstance(normalised, dict):
            return normalised
        product_ids = [product_id for product_id, _ in normalised]
        products = {product.id: product for product in session.scalars(select(Product).where(Product.id.in_(product_ids)))}
        held_quantities = _active_hold_quantities(session, product_ids, now)
        for product_id, quantity in normalised:
            if products[product_id].stock - held_quantities.get(product_id, 0) < quantity:
                return _error("OUT_OF_STOCK", "One or more requested products are out of stock")

        expires_at = now + timedelta(minutes=get_settings().stock_hold_minutes)
        order = Order(
            conversation_id=conversation_id,
            status=OrderStatus.PENDING,
            delivery_fee_kobo=int(quote["deliveryFeeKobo"]),
            total_kobo=int(quote["totalKobo"]),
            delivery_area=str(quote["deliveryArea"]),
            expires_at=expires_at,
        )
        session.add(order)
        session.flush()
        order.paystack_reference = f"SW-{order.id.replace('-', '')[:12].upper()}"
        for line in quote["lines"]:
            session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=str(line["productId"]),
                    quantity=int(line["quantity"]),
                    unit_price_kobo=int(line["unitPriceKobo"]),
                )
            )
        for product_id, quantity in normalised:
            session.add(StockHold(product_id=product_id, order_id=order.id, quantity=quantity, expires_at=expires_at))
    return {
        "orderId": order.id,
        "reference": order.paystack_reference,
        "amountKobo": order.total_kobo,
        "expiresAt": order.expires_at,
    }


def mark_order_paid(session: Session, reference: str, amount_kobo: int) -> dict[str, Any]:
    """Idempotently capture a matching payment and consume the associated stock once."""
    transaction = session.begin_nested() if session.in_transaction() else session.begin()
    with transaction:
        order = session.scalar(select(Order).where(Order.paystack_reference == reference))
        if order is None:
            return _error("NOT_FOUND", "Order reference was not found")
        if not isinstance(amount_kobo, int) or isinstance(amount_kobo, bool) or amount_kobo != order.total_kobo:
            return _error("AMOUNT_MISMATCH", "Payment amount does not match the order total")
        updated = session.execute(
            update(Order)
            .where(Order.id == order.id, Order.status == OrderStatus.PENDING)
            .values(status=OrderStatus.PAID)
        )
        if updated.rowcount != 1:
            return {"paid": False, "orderId": order.id}
        holds = list(session.scalars(select(StockHold).where(StockHold.order_id == order.id)))
        for hold in holds:
            session.execute(update(Product).where(Product.id == hold.product_id).values(stock=Product.stock - hold.quantity))
        session.execute(delete(StockHold).where(StockHold.order_id == order.id))
    return {"paid": True, "orderId": order.id}
