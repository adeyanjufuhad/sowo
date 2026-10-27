"""Which vendor a conversation belongs to."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Vendor


def default_vendor(session: Session) -> Vendor | None:
    """The oldest vendor. A stand-in until WhatsApp numbers are mapped to vendors."""
    return session.scalar(select(Vendor).order_by(Vendor.created_at, Vendor.name, Vendor.id).limit(1))
