import pytest

from app.services.guard import (
    amounts_in,
    claims_payment_received,
    find_unbacked_amounts,
    kobo_values,
    looks_like_pidgin,
)
from app.services.money import format_naira


@pytest.mark.parametrize(
    ("text", "kobo"),
    [
        ("The loafers are ₦45,000.", [4_500_000]),
        ("Total is N43,500, delivery N2,500", [4_350_000, 250_000]),
        ("NGN 41000 only", [4_100_000]),
        ("abeg do am 35k", [3_500_000]),
        ("I fit pay 40 thousand", [4_000_000]),
        ("45,000 naira", [4_500_000]),
        ("₦43,500.50 exactly", [4_350_050]),
        ("Delivery to Ikeja, ₦2,500, so ₦43,500, ok?", [250_000, 4_350_000]),
        ("size 43, 2 pairs, 1 to 2 days, order SW-1043", []),
        ("Na size 43 we get", []),
    ],
)
def test_amounts_are_found_in_every_way_buyers_and_models_write_them(text: str, kobo: list[int]) -> None:
    assert amounts_in(text) == kobo


def test_only_amounts_nobody_returned_are_flagged() -> None:
    allowed = {4_500_000, 4_300_000}
    assert find_unbacked_amounts("They are ₦45,000, or ₦43,000 for you", allowed) == []
    assert find_unbacked_amounts("Special price: ₦30,000", allowed) == [3_000_000]


def test_kobo_values_are_collected_from_nested_tool_calls() -> None:
    trace = {
        "tool": "get_quote",
        "input": {"items": [{"productId": "p1", "quantity": 1}], "deliveryArea": "Ikeja"},
        "output": {
            "quoteId": "q_1",
            "lines": [{"unitPriceKobo": 4_100_000, "lineTotalKobo": 4_100_000}],
            "deliveryFeeKobo": 250_000,
            "totalKobo": 4_350_000,
        },
    }
    assert kobo_values(trace) == {4_100_000, 250_000, 4_350_000}


@pytest.mark.parametrize(
    "text",
    [
        "Payment confirmed, thank you!",
        "We have received your payment.",
        "I don confirm your payment o.",
        "Your transfer has been received.",
        "Money don land, we dey pack am.",
    ],
)
def test_claims_that_money_arrived_are_caught(text: str) -> None:
    assert claims_payment_received(text)


@pytest.mark.parametrize(
    "text",
    [
        "We'll confirm the moment Paystack reports it.",
        "Once Paystack confirm say the money land, I go tell you.",
        "As soon as the payment is confirmed we will pack it.",
        "Pay here: https://paystack.test/pay/SW-1",
        "No need for a screenshot, Paystack tells us.",
    ],
)
def test_promises_to_confirm_later_are_fine(text: str) -> None:
    assert not claims_payment_received(text)


def test_pidgin_is_recognised() -> None:
    assert looks_like_pidgin("abeg do am 35k")
    assert looks_like_pidgin("I dey Ikeja")
    assert not looks_like_pidgin("Could you do 35k please?")


@pytest.mark.parametrize(
    ("kobo", "text"),
    [(4_350_000, "₦43,500"), (250_000, "₦2,500"), (0, "₦0"), (4_350_050, "₦43,500.50"), (-250_000, "-₦2,500")],
)
def test_naira_formatting(kobo: int, text: str) -> None:
    assert format_naira(kobo) == text


def test_naira_formatting_refuses_floats_and_bools() -> None:
    with pytest.raises(TypeError):
        format_naira(43_500.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        format_naira(True)
