"""Which vendor a conversation belongs to, and what a vendor has set up."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Vendor

BANK_ACCOUNT_NUMBER = re.compile(r"\d{10}")  # a Nigerian NUBAN


def vendor_for_number(session: Session, phone_number_id: str) -> Vendor | None:
    """The vendor whose WhatsApp business number received a message. Unknown numbers belong to nobody."""
    if not phone_number_id:
        return None
    return session.scalar(select(Vendor).where(Vendor.whatsapp_phone_number_id == phone_number_id))


def demo_vendor(session: Session, settings: Settings) -> Vendor | None:
    """The shop the unauthenticated simulator talks to. Only used when SIMULATOR_ENABLED is on."""
    return session.scalar(select(Vendor).where(Vendor.name == settings.simulator_vendor_name))


def owner_name(vendor: Vendor) -> str:
    """How the assistant and the receipts refer to the person behind the shop."""
    return (vendor.owner_name or "").strip() or vendor.name


def vendor_bank(vendor: Vendor) -> dict[str, str] | None:
    """The vendor's account for bank transfers, or None if it isn't (properly) set up."""
    bank = {
        "bankName": (vendor.bank_name or "").strip(),
        "accountName": (vendor.bank_account_name or "").strip(),
        "accountNumber": re.sub(r"\s", "", vendor.bank_account_number or ""),
    }
    if not bank["bankName"] or not bank["accountName"] or not BANK_ACCOUNT_NUMBER.fullmatch(bank["accountNumber"]):
        return None
    return bank
