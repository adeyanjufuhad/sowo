"""Checks on the model's final reply, so the server's decisions can't be overridden by wording.

The model may only phrase what the tools returned. These functions find the two ways it could break that:
quoting a price no tool produced, and telling the buyer a payment arrived when none did.
"""

import re
from typing import Any

# "₦43,500", "N43500", "NGN 43,500", "43k", "43 thousand", "43,500 naira"
_AMOUNT = re.compile(
    r"(?:(?:₦|NGN\s?|\bN)\s?(?P<a>\d[\d,]*(?:\.\d+)?)(?P<ak>\s?k\b|\s?thousand\b)?)"
    r"|(?:(?P<b>\d[\d,]*(?:\.\d+)?)(?P<bk>\s?k\b|\s?thousand\b|\s?naira\b))",
    re.IGNORECASE,
)


def amounts_in(text: str) -> list[int]:
    """Every naira amount written in `text`, as integer kobo."""
    found: list[int] = []
    for match in _AMOUNT.finditer(text):
        raw = (match.group("a") or match.group("b") or "").rstrip(",").replace(",", "")
        suffix = (match.group("ak") or match.group("bk") or "").strip().lower()
        try:
            value = float(raw)
        except ValueError:
            continue
        if suffix in {"k", "thousand"}:
            value *= 1000
        found.append(round(value * 100))
    return found


# Buyers haggle in thousands without saying so: "make it 41 na" after a ₦43,000 counter means ₦41,000.
_SHORTHAND = re.compile(r"(?<![\d,.₦])\b(?P<n>[1-9]\d{0,2})\b(?![\d,.]|\s?(?:k\b|thousand|naira))", re.IGNORECASE)
_PRICE_CUE = re.compile(
    r"\b(?:make\s+it|make\s+am|do\s+am|do\s+it|fit\s+do|can\s+you\s+do|last|price|offer|pay|reduce|how\s+about|"
    r"abeg|oya|give\s+me|i\s+go\s+give)\b",
    re.IGNORECASE,
)
_NOT_A_PRICE_BEFORE = re.compile(r"(?:size|sz|no\.?|number|qty|quantity|x|order|ref)\s*$", re.IGNORECASE)
_NOT_A_PRICE_AFTER = re.compile(r"^\s*(?:pairs?|pcs|pieces?|days?|weeks?|hours?|mins?|size|yrs?|years?)\b", re.IGNORECASE)


def offered_amounts(text: str) -> list[int]:
    """Prices a buyer offered, in kobo: every written amount, plus "41" meaning ₦41,000 in a price ask.

    The shorthand only counts in a message that reads like haggling, and never for a size, a count or a reference,
    so "Na size 43" offers nothing.
    """
    found = amounts_in(text)
    if not _PRICE_CUE.search(text):
        return found
    for match in _SHORTHAND.finditer(text):
        if _NOT_A_PRICE_BEFORE.search(text[: match.start()]) or _NOT_A_PRICE_AFTER.match(text[match.end() :]):
            continue
        found.append(int(match.group("n")) * 1000 * 100)
    return found


def kobo_values(data: Any) -> set[int]:
    """Every integer stored under a key ending in 'Kobo', anywhere inside a tool call's input or output."""
    values: set[int] = set()
    if isinstance(data, dict):
        for key, item in data.items():
            if isinstance(key, str) and key.endswith("Kobo") and isinstance(item, int):
                values.add(item)
            else:
                values |= kobo_values(item)
    elif isinstance(data, list):
        for item in data:
            values |= kobo_values(item)
    return values


def find_unbacked_amounts(reply: str, allowed_kobo: set[int]) -> list[int]:
    """Amounts in `reply` that no tool returned and the buyer didn't say, in kobo."""
    return [amount for amount in amounts_in(reply) if amount not in allowed_kobo]


_PAYMENT_CLAIM = re.compile(
    r"\b(?:payment|transfer|money)\s+(?:is\s+|has\s+|don\s+)?(?:been\s+)?"
    r"(?:confirm(?:ed)?|receive[d]?|land(?:ed)?|successful)\b"
    r"|\b(?:we|i)\s+(?:have\s+|don\s+)?(?:receive[d]?|confirm(?:ed)?)\s+your\s+(?:payment|transfer|money)\b",
    re.IGNORECASE,
)
_CONDITIONAL = re.compile(r"\b(?:once|when|until|after|if|as soon as|before|wen)\b", re.IGNORECASE)


def claims_payment_received(text: str) -> bool:
    """True if the reply says payment has arrived (as opposed to 'we'll confirm once it lands')."""
    for match in _PAYMENT_CLAIM.finditer(text):
        lead_in = text[max(0, match.start() - 40) : match.start()]
        if not _CONDITIONAL.search(lead_in):
            return True
    return False


_PIDGIN = re.compile(r"\b(?:abeg|dey|wetin|una|oga|wan|abi|sha|na|don|sef|wahala|wey|o)\b", re.IGNORECASE)


def looks_like_pidgin(text: str) -> bool:
    return bool(_PIDGIN.search(text))
