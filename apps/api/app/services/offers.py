from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Offer, Product
from app.models import OfferDecision as StoredOfferDecision
from app.services.haggling import OfferDecision, evaluate_offer


def evaluate_and_persist_offer(
    session: Session,
    *,
    conversation_id: str,
    product: Product,
    offer_kobo: int,
) -> OfferDecision:
    """Store a buyer offer and return the server-owned negotiation decision."""
    prior_below_floor_offers = session.scalar(
        select(func.count(Offer.id)).where(
            Offer.conversation_id == conversation_id,
            Offer.product_id == product.id,
            Offer.amount_kobo < product.floor_price_kobo,
        )
    )
    decision = evaluate_offer(
        product.price_kobo,
        product.floor_price_kobo,
        offer_kobo,
        int(prior_below_floor_offers or 0),
    )
    session.add(
        Offer(
            conversation_id=conversation_id,
            product_id=product.id,
            amount_kobo=offer_kobo,
            decision=StoredOfferDecision(decision.action.upper()),
        )
    )
    session.commit()
    return decision
