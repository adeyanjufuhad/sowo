from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, create_database_engine
from app.models import Conversation, Offer, Product, Vendor
from app.services.offers import evaluate_and_persist_offer


def test_offer_service_persists_and_counts_below_floor_offers(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'offers.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        vendor = Vendor(name="Test vendor")
        session.add(vendor)
        session.flush()
        product = Product(vendor_id=vendor.id, sku="TEST-LOAFER", name="Test loafer", description="Test", size="43", colour="Black", price_kobo=4500000, floor_price_kobo=4000000, stock=1)
        conversation = Conversation(vendor_id=vendor.id, customer_phone="2348012345678")
        session.add_all([product, conversation])
        session.commit()

        first = evaluate_and_persist_offer(session, conversation_id=conversation.id, product=product, offer_kobo=3500000)
        second = evaluate_and_persist_offer(session, conversation_id=conversation.id, product=product, offer_kobo=3600000)
        third = evaluate_and_persist_offer(session, conversation_id=conversation.id, product=product, offer_kobo=3700000)

        assert [first.action, second.action, third.action] == ["counter", "counter", "handoff"]
        assert session.scalars(select(Offer).where(Offer.conversation_id == conversation.id)).all()


def test_rejected_offer_is_persisted_and_counts_toward_handoff(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'rejects.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        vendor = Vendor(name="Another vendor")
        session.add(vendor)
        session.flush()
        product = Product(vendor_id=vendor.id, sku="TEST-SLIDE", name="Test slide", description="Test", size="42", colour="Blue", price_kobo=2000000, floor_price_kobo=1600000, stock=1)
        conversation = Conversation(vendor_id=vendor.id, customer_phone="2348098765432")
        session.add_all([product, conversation])
        session.commit()

        rejected = evaluate_and_persist_offer(session, conversation_id=conversation.id, product=product, offer_kobo=100000)
        evaluate_and_persist_offer(session, conversation_id=conversation.id, product=product, offer_kobo=1500000)
        handoff = evaluate_and_persist_offer(session, conversation_id=conversation.id, product=product, offer_kobo=1500000)

        assert rejected.action == "reject"
        assert handoff.action == "handoff"
