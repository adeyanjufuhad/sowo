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
    """The shop the unauthenticated simulator talks to. Only used when SIMULATOR_ENABLED is on.

    SIMULATOR_VENDOR_NAME finds it by name the first time; after that the shop is remembered under that setting, so
    renaming it in its settings keeps /try working. Pointing the setting at another shop's name moves the demo there.
    """
    key = settings.simulator_vendor_name
    remembered = session.scalar(select(Vendor).where(Vendor.simulator_key == key))
    if remembered is not None:
        return remembered
    named = session.scalar(select(Vendor).where(Vendor.name == key))
    if named is not None:
        named.simulator_key = key
        session.commit()
    return named


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
