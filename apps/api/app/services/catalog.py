from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, Product, StockHold


def search_catalog(session: Session, vendor_id: str, query: str) -> dict[str, list[dict[str, int | str]]]:
    """Return a deliberately narrow, model-safe projection of one vendor's matching products."""
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
        + " "
        + func.coalesce(Product.category, "")
    )
    statement = select(
        Product.id,
        Product.sku,
        Product.name,
        Product.category,
        Product.price_kobo,
        Product.stock,
        func.coalesce(active_holds.c.held, 0).label("held"),
    ).outerjoin(active_holds, active_holds.c.product_id == Product.id).where(
        Product.vendor_id == vendor_id, Product.archived_at.is_(None)
    )
    for word in query.casefold().split():
        statement = statement.where(searchable.like(f"%{_singular(word)}%"))

    results = []
    for product_id, sku, name, category, price_kobo, stock, held in session.execute(statement):
        hit: dict[str, int | str] = {
            "productId": product_id,
            "sku": sku,
            "name": name,
            "priceKobo": price_kobo,
            "stockOnHand": max(0, stock - held),
        }
        if category:
            hit["category"] = category
        results.append(hit)
    return {"results": results}


def _singular(word: str) -> str:
    """So a buyer's "shoes" finds a category the vendor called "Shoe" ("shoe" already finds "Shoes")."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def vendor_categories(session: Session, vendor_id: str) -> list[str]:
    """The categories this vendor sells, each once whatever the capitals, for the assistant's prompt."""
    names = session.scalars(
        select(Product.category)
        .where(Product.vendor_id == vendor_id, Product.archived_at.is_(None), Product.category.is_not(None))
        .distinct()
    )
    unique: dict[str, str] = {}
    for name in names:
        if name and name.strip():
            unique.setdefault(name.strip().casefold(), name.strip())
    return sorted(unique.values(), key=str.casefold)
