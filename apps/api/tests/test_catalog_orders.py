import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, create_database_engine
from app.models import (
    Conversation,
    DeliveryZone,
    Offer,
    OfferDecision,
    Order,
    OrderStatus,
    Product,
    Vendor,
)
from app.services.catalog import search_catalog
from app.services.orders import create_order_with_hold, expire_holds, get_quote, mark_order_paid


def make_session(tmp_path: Path) -> Session:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'orders.db'}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    vendor = Vendor(name="Ada's Footwear")
    session.add(vendor)
    session.flush()
    session.add_all(
        [
            Product(
                vendor_id=vendor.id,
                sku="LOAF-BLK-43",
                name="Black Leather Loafers, size 43",
                description="Soft black leather office shoes",
                size="43",
                colour="Black",
                price_kobo=4500000,
                floor_price_kobo=4000000,
                stock=1,
            ),
            DeliveryZone(vendor_id=vendor.id, area="Ikeja", fee_kobo=250000),
            Conversation(vendor_id=vendor.id, customer_phone="2348012345678"),
            Conversation(vendor_id=vendor.id, customer_phone="2348098765432"),
        ]
    )
    session.commit()
    return session


def test_quote_uses_ikeja_fee_and_accepted_offer_price(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        product = session.scalar(select(Product))
        conversation = session.scalars(select(Conversation).order_by(Conversation.customer_phone)).first()
        assert product is not None and conversation is not None
        session.add(
            Offer(
                conversation_id=conversation.id,
                product_id=product.id,
                amount_kobo=4100000,
                decision=OfferDecision.ACCEPT,
            )
        )
        session.commit()

        quote = get_quote(session, conversation.id, [{"product_id": product.id, "qty": 1}], "Ikeja")

        assert quote["lines"][0]["unitPriceKobo"] == 4100000
        assert quote["deliveryFeeKobo"] == 250000
        assert quote["totalKobo"] == 4350000


def test_quote_falls_back_to_list_price_and_rejects_unknown_area(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        product = session.scalar(select(Product))
        conversation = session.scalar(select(Conversation))
        assert product is not None and conversation is not None

        quote = get_quote(session, conversation.id, [{"product_id": product.id, "qty": 1}], "Ikeja")
        missing_area = get_quote(session, conversation.id, [{"product_id": product.id, "qty": 1}], "Abuja")

        assert quote["lines"][0]["unitPriceKobo"] == 4500000
        assert missing_area["error"]["code"] == "UNKNOWN_DELIVERY_AREA"


def test_hold_blocks_second_buyer_for_last_pair(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        product = session.scalar(select(Product))
        conversations = session.scalars(select(Conversation).order_by(Conversation.customer_phone)).all()
        assert product is not None

        first = create_order_with_hold(session, conversations[0].id, [{"product_id": product.id, "qty": 1}], "Ikeja")
        second = create_order_with_hold(session, conversations[1].id, [{"product_id": product.id, "qty": 1}], "Ikeja")

        assert "orderId" in first
        assert second["error"]["code"] == "OUT_OF_STOCK"


def test_expiry_releases_stock_hold(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        product = session.scalar(select(Product))
        conversations = session.scalars(select(Conversation).order_by(Conversation.customer_phone)).all()
        assert product is not None

        created = create_order_with_hold(session, conversations[0].id, [{"product_id": product.id, "qty": 1}], "Ikeja")
        order = session.get(Order, created["orderId"])
        assert order is not None and order.expires_at is not None
        expire_holds(session, order.expires_at + timedelta(seconds=1))
        session.commit()

        next_order = create_order_with_hold(session, conversations[1].id, [{"product_id": product.id, "qty": 1}], "Ikeja")
        assert order.status == OrderStatus.EXPIRED
        assert "orderId" in next_order


def test_payment_is_idempotent_and_deducts_stock_once(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        product = session.scalar(select(Product))
        conversation = session.scalar(select(Conversation))
        assert product is not None and conversation is not None
        created = create_order_with_hold(session, conversation.id, [{"product_id": product.id, "qty": 1}], "Ikeja")

        first = mark_order_paid(session, created["reference"], created["amountKobo"])
        second = mark_order_paid(session, created["reference"], created["amountKobo"])
        session.refresh(product)

        assert first["paid"] is True
        assert second["paid"] is False
        assert product.stock == 0


def test_amount_mismatch_is_rejected(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        product = session.scalar(select(Product))
        conversation = session.scalar(select(Conversation))
        assert product is not None and conversation is not None
        created = create_order_with_hold(session, conversation.id, [{"product_id": product.id, "qty": 1}], "Ikeja")

        result = mark_order_paid(session, created["reference"], created["amountKobo"] - 1)
        order = session.get(Order, created["orderId"])

        assert result["error"]["code"] == "AMOUNT_MISMATCH"
        assert order is not None and order.status == OrderStatus.PENDING


def test_catalog_result_never_contains_floor_price(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        vendor_id = session.scalars(select(Vendor.id)).one()
        result = search_catalog(session, vendor_id, "size 43 black loafers")
        encoded = json.dumps(result)

        assert result["results"] == [
            {
                "productId": result["results"][0]["productId"],
                "sku": "LOAF-BLK-43",
                "name": "Black Leather Loafers, size 43",
                "priceKobo": 4500000,
                "stockOnHand": 1,
            }
        ]
        assert "floor" not in encoded.casefold()
        assert 4000000 not in result["results"][0].values()
