"""The rules, as plain functions of text. No database, no model: easy to test with real-sounding messages."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Severity = Literal["medium", "high"]


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    evidence: str  # the words that matched, for the vendor


# What the vendor reads in the dashboard for each rule.
WARNINGS = {
    "SECRET_REQUEST": "Asked for a code, PIN, BVN or password. Never share these.",
    "IMPERSONATION": "Claims to be from a bank, Paystack, WhatsApp or a delivery company. Don't act on it.",
    "PHISHING_LINK": "Sent a link to a site Sowo doesn't know. Don't open it or pay through it.",
    "RELEASE_BEFORE_PAYMENT": "Wants the goods before paying. Don't ship until the money is in your account.",
    "UNVERIFIED_PAYMENT": "Unverified screenshot. Check your bank app before you pack.",
    "REPEATED_FAILED_PAYMENTS": "Several payments in this chat failed or expired.",
}

_I = re.IGNORECASE
_SECRET = r"(?:otp|one[- ]time (?:password|code|pin)|pin|bvn|cvv|password|passcode|(?:\d[- ]?digit\s+)?code|token)"
_SECRET_ASKS = [
    # "send me the code", "abeg give me your BVN", "share the OTP", "read me the 6 digit code"
    re.compile(
        rf"\b(?:send|give|tell|share|forward|drop|read|provide|confirm|type)\b(?:\s+(?!and\b)\w+){{0,4}}?\s+{_SECRET}\b", _I
    ),
    # "the code wey dem send you", "the OTP that the bank sent"
    re.compile(r"\b(?:otp|code|pin)\s+(?:wey|that|which)\s+(?:dem|they|the bank|bank|paystack|e|una)\s+(?:send|sent|go send)", _I),
    # "what's your PIN?", "wetin be your BVN"
    re.compile(r"\b(?:what(?:'s| is)|wetin be)\s+(?:your|ur|una)\s+(?:\w+\s+)?(?:otp|pin|bvn|password|cvv)\b", _I),
]
# A location pin or a promo code is not a secret, and "never share your PIN" is advice, not a request.
_NOT_SECRET = re.compile(r"\b(?:location|promo|discount|coupon|referral|zip|postal|post)\b", _I)
_NEGATED = re.compile(r"\b(?:never|no|not|don't|dont|do not|nor)\s*$", _I)

_COMPANIES = (
    r"(?:paystack|flutterwave|opay|palmpay|moniepoint|kuda|cbn|efcc|whatsapp|meta|(?:your|ur|una|the) bank|gtbank|gtb|"
    r"access bank|zenith|first ?bank|uba|wema|sterling|fidelity|customer (?:care|service|support))"
)
_IMPERSONATION = [
    # "I'm from Paystack", "I be staff from your bank", "I dey call from GTBank"
    re.compile(rf"\b(?:i(?:'m| am| be| dey)|this is|na)\s+(?:\w+\s+){{0,2}}?(?:from|with|call(?:ing)? from)\s+{_COMPANIES}\b", _I),
    # "This is Paystack support"
    re.compile(r"\b(?:this is|na)\s+(?:paystack|flutterwave|opay|palmpay|moniepoint|kuda|whatsapp)\s+(?:support|team|security|customer care)\b", _I),
]
# "I be the delivery agent... pay the delivery fee first": a courier who wants money before handing over.
_COURIER = re.compile(
    r"\b(?:i(?:'m| am| be)|this is|na)\s+(?:the\s+|your\s+|una\s+)?(?:delivery|dispatch|logistics|courier)"
    r"(?:\s+(?:agent|rider|man|company|guy|person))?\b|\bi be (?:the )?rider\b",
    _I,
)
_PAY_FIRST = re.compile(r"\b(?:pay|send|transfer)\b.{0,40}\b(?:first|before)\b", _I)

_RELEASE_FIRST = [
    # "ship am first, I go pay", "send the shoes first", "deliver it before I transfer"
    re.compile(
        r"\b(?:send|ship|deliver|dispatch|release|bring)\b(?:\s+\w+){0,3}?\s+(?:first|before (?:i|we) (?:pay|transfer))\b", _I
    ),
    # "I'll pay when it reaches me", "I go transfer once e reach"
    re.compile(
        r"\bi(?:'ll| will| go)\s+(?:pay|transfer|send (?:the )?money)\b(?:\s+\w+){0,2}?\s+(?:after|when|once)\s+"
        r"(?:i|it|e|am|the goods|the item)\s+(?:receive|reach|arrive|collect|get|see|deliver)",
        _I,
    ),
]
# Asking for the bank details or a picture first is ordinary buying.
_FINE_FIRST = re.compile(r"\b(?:account|details|number|link|pic|picture|photo|video|price|size)\b", _I)

_PAID_CLAIMS = [
    re.compile(
        r"\b(?:i(?:'ve| have)|i don|we don|i just|i already)\s+(?:just\s+|already\s+)?"
        r"(?:pay|paid|transfer(?:red)?|send the money|sent the money)\b"
        r"|\bi\s+(?:paid|transferred|sent the money)\b",
        _I,
    ),
    re.compile(r"\b(?:payment|transfer|money)\s+(?:don\s+)?(?:done|sent|don go|don land|successful|has gone)\b", _I),
    re.compile(r"\bcheck\s+(?:your|ur|una)\s+(?:account|alert|bank|phone|app)\b", _I),
]

_TLDS = r"(?:com|net|org|ng|ly|io|co|xyz|top|link|app|me|info|site|online|shop|live|click|ru|cn|biz|vip|cc|tk|gl|gd|to|sh)"
_URL = re.compile(rf"(?<![@\w.])(?:https?://)?((?:[a-z0-9-]+\.)+{_TLDS})\b(?:/\S*)?", _I)


def _first(patterns: Iterable[re.Pattern[str]], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def asks_for_secrets(text: str) -> str | None:
    """The words asking for a code, PIN, BVN or password, if any. Also used to keep such words out of Sowo's voice."""
    for pattern in _SECRET_ASKS:
        for match in pattern.finditer(text):
            if _NOT_SECRET.search(text[max(0, match.start() - 30) : match.end() + 30]):
                continue
            if _NEGATED.search(text[max(0, match.start() - 15) : match.start()]):
                continue
            return match.group(0)
    return None


def claims_payment(text: str) -> bool:
    return _first(_PAID_CLAIMS, text) is not None


def unknown_links(text: str, allowed_domains: Iterable[str]) -> list[str]:
    allowed = [domain.lower().lstrip(".") for domain in allowed_domains]
    found = []
    for match in _URL.finditer(text):
        host = match.group(1).lower().removeprefix("www.")
        if not any(host == domain or host.endswith("." + domain) for domain in allowed):
            found.append(match.group(0))
    return found


def scan_text(text: str, allowed_domains: Iterable[str]) -> list[Finding]:
    """Everything suspicious in one buyer message."""
    findings: list[Finding] = []
    if secret := asks_for_secrets(text):
        findings.append(Finding("SECRET_REQUEST", "high", secret))
    if posing := _first(_IMPERSONATION, text):
        findings.append(Finding("IMPERSONATION", "high", posing))
    elif (courier := _COURIER.search(text)) and _PAY_FIRST.search(text):
        findings.append(Finding("IMPERSONATION", "high", courier.group(0)))
    links = unknown_links(text, allowed_domains)
    if links:
        findings.append(Finding("PHISHING_LINK", "medium", ", ".join(links)[:300]))
    release = _first(_RELEASE_FIRST, text)
    if release and not _FINE_FIRST.search(release):
        findings.append(Finding("RELEASE_BEFORE_PAYMENT", "medium", release))
    return findings
