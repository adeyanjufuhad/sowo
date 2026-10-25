import pytest

from app.services.haggling import evaluate_offer


def test_demo_offer_counters_and_accepts() -> None:
    counter = evaluate_offer(4500000, 4000000, 3500000, 0)
    accepted = evaluate_offer(4500000, 4000000, 4100000, 0)
    assert (counter.action, counter.price_kobo) == ("counter", 4300000)
    assert (accepted.action, accepted.price_kobo) == ("accept", 4100000)


def test_exact_floor_accepts_and_above_list_is_capped() -> None:
    assert evaluate_offer(4500000, 4000000, 4000000, 0).price_kobo == 4000000
    assert evaluate_offer(4500000, 4000000, 5000000, 0).price_kobo == 4500000


@pytest.mark.parametrize("list_price,floor_price", [(4500000, 4000000), (1000000, 600000), (850000, 850000)])
def test_counters_never_go_below_floor(list_price: int, floor_price: int) -> None:
    for offer in range(max(1, list_price // 2), floor_price, 50000):
        decision = evaluate_offer(list_price, floor_price, offer, 0)
        assert decision.action == "counter"
        assert isinstance(decision.price_kobo, int)
        assert floor_price <= decision.price_kobo <= list_price


def test_counters_are_non_increasing_across_rounds() -> None:
    first = evaluate_offer(4500000, 4000000, 3900000, 0)
    second = evaluate_offer(4500000, 4000000, 3900000, 1)
    assert first.price_kobo is not None
    assert second.price_kobo is not None
    assert second.price_kobo <= first.price_kobo


def test_third_below_floor_offer_hands_off() -> None:
    decision = evaluate_offer(4500000, 4000000, 3900000, 2)
    assert decision.action == "handoff"
    assert decision.price_kobo is None


@pytest.mark.parametrize("offer", [0, -1, 2249999])
def test_absurd_offers_are_rejected(offer: int) -> None:
    decision = evaluate_offer(4500000, 4000000, offer, 0)
    assert decision.action == "reject"
    assert decision.price_kobo is None
