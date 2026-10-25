from dataclasses import dataclass
from typing import Literal

Action = Literal["accept", "counter", "reject", "handoff"]
_ROUNDING_KOBO = 50_000


@dataclass(frozen=True)
class OfferDecision:
    """Server-calculated negotiation result safe to pass to the reply layer."""

    action: Action
    price_kobo: int | None


def _round_up_to_500_naira(amount_kobo: int) -> int:
    return ((amount_kobo + _ROUNDING_KOBO - 1) // _ROUNDING_KOBO) * _ROUNDING_KOBO


def evaluate_offer(
    list_price_kobo: int,
    floor_price_kobo: int,
    offer_kobo: int,
    prior_below_floor_offers: int,
) -> OfferDecision:
    """Evaluate an offer without exposing any protected pricing information."""
    values = (list_price_kobo, floor_price_kobo, offer_kobo, prior_below_floor_offers)
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
        return OfferDecision(action="reject", price_kobo=None)
    if (
        list_price_kobo <= 0
        or floor_price_kobo <= 0
        or floor_price_kobo > list_price_kobo
        or prior_below_floor_offers < 0
    ):
        return OfferDecision(action="reject", price_kobo=None)
    if offer_kobo <= 0 or offer_kobo < list_price_kobo // 2:
        return OfferDecision(action="reject", price_kobo=None)
    if offer_kobo >= floor_price_kobo:
        return OfferDecision(action="accept", price_kobo=min(offer_kobo, list_price_kobo))
    if prior_below_floor_offers >= 2:
        return OfferDecision(action="handoff", price_kobo=None)

    gap_kobo = list_price_kobo - floor_price_kobo
    concession_percent = 40 if prior_below_floor_offers == 0 else 75
    counter_kobo = list_price_kobo - (gap_kobo * concession_percent // 100)
    counter_kobo = _round_up_to_500_naira(counter_kobo)
    counter_kobo = min(list_price_kobo, max(floor_price_kobo, counter_kobo))
    return OfferDecision(action="counter", price_kobo=counter_kobo)
