"""Vendor accounts: Argon2 password hashes and revocable dashboard sessions.

The web app keeps the session token in an httpOnly cookie on its own domain and forwards it as a bearer token.
Here only a SHA-256 hash of the token is stored, and a session can be revoked by deleting its row.
"""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Vendor, VendorSession

SESSION_DAYS = 30
TOUCH_EVERY = timedelta(minutes=5)  # the dashboard polls every few seconds; don't write on each poll
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128  # Argon2 would take any length; this stops absurd requests, not real passwords
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_hasher = PasswordHasher()  # Argon2id with the library's recommended parameters


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return len(email) <= 254 and bool(_EMAIL.match(email))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


@cache
def _dummy_hash() -> str:
    return _hasher.hash("sowo-no-such-account")


def check_password(vendor: Vendor | None, password: str) -> bool:
    """Verify a login. A missing account still costs one hash, so response time doesn't reveal who has an account."""
    stored = vendor.password_hash if vendor is not None and vendor.password_hash else None
    try:
        _hasher.verify(stored or _dummy_hash(), password)
    except (VerificationError, InvalidHashError):
        return False
    if stored is None:
        return False
    if vendor is not None and _hasher.check_needs_rehash(stored):
        vendor.password_hash = _hasher.hash(password)  # parameters were raised since this hash was made
    return True


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def create_session(session: Session, vendor: Vendor, now: datetime | None = None) -> tuple[str, datetime]:
    """Start a session. Returns the token (shown once, never stored) and when it expires."""
    now = now or datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(days=SESSION_DAYS)
    session.add(
        VendorSession(
            vendor_id=vendor.id, token_hash=_digest(token), created_at=now, expires_at=expires_at, last_used_at=now
        )
    )
    session.commit()
    return token, expires_at


def find_vendor(session: Session, token: str, now: datetime | None = None) -> Vendor | None:
    """The vendor a live session token belongs to, or None. Expired sessions are removed when they are met."""
    now = now or datetime.now(UTC)
    row = session.scalar(select(VendorSession).where(VendorSession.token_hash == _digest(token)))
    if row is None:
        return None
    if _utc(row.expires_at) <= now:
        session.delete(row)
        session.commit()
        return None
    if now - _utc(row.last_used_at) > TOUCH_EVERY:
        row.last_used_at = now
    vendor = session.get(Vendor, row.vendor_id)
    session.commit()  # also ends the read transaction, so routes can open their own
    return vendor


def end_session(session: Session, token: str) -> None:
    session.execute(delete(VendorSession).where(VendorSession.token_hash == _digest(token)))
    session.commit()


def end_all_sessions(session: Session, vendor: Vendor) -> None:
    session.execute(delete(VendorSession).where(VendorSession.vendor_id == vendor.id))
    session.commit()
