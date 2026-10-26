from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, Product, StockHold


def search_catalog(session: Session, query: str) -> dict[str, list[dict[str, int | str]]]:
    """Return a deliberately narrow, model-safe projection of matching products."""
    from app.services.orders import expire_holds

    expire_holds(session)
    now = datetime.now(UTC)
    active_holds = (
        select(StockHold.product_id, func.coalesce(func.sum(StockHold.quantity), 0).label("held"))
        .join(Order, Order.id == StockHold.order_id)
        .where(Order.status == OrderStatus.PENDING, StockHold.expires_at > now)
        .group_by(StockHold.product_id)
        .subquery()
    )

    searchable = func.lower(
        Product.name
        + " "
        + Product.description
        + " "
        + func.coalesce(Product.size, "")
        + " "
        + func.coalesce(Product.colour, "")
    )
    statement = select(
        Product.id,
        Product.name,
        Product.price_kobo,
        Product.stock,
        func.coalesce(active_holds.c.held, 0).label("held"),
    ).outerjoin(active_holds, active_holds.c.product_id == Product.id)
    for word in query.casefold().split():
        statement = statement.where(searchable.like(f"%{word}%"))

    results = []
    for product_id, name, price_kobo, stock, held in session.execute(statement):
        results.append(
            {
                "productId": product_id,
                "name": name,
                "priceKobo": price_kobo,
                "stockOnHand": max(0, stock - held),
            }
        )
    return {"results": results}
