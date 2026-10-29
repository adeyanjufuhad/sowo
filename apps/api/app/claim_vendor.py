"""Give an existing vendor (such as the demo shop, or one made before accounts existed) a login.

    python -m app.claim_vendor "Ada's Footwear" ada@example.com
    python -m app.claim_vendor "Ada's Footwear" demo@example.com --replace

The password is asked for on the terminal, so it never lands in shell history. --replace changes the email and
password of a vendor that already has a login, and signs out every session it had, so the old details stop working
everywhere at once.
"""

import argparse
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.models import Vendor
from app.services import auth


def claim(session: Session, business_name: str, email: str, password: str, replace: bool = False) -> Vendor:
    vendor = session.scalar(select(Vendor).where(Vendor.name == business_name))
    if vendor is None:
        raise ValueError(f"No vendor is called {business_name!r}")
    if vendor.password_hash and not replace:
        raise ValueError(f"{business_name!r} already has a login; pass --replace to change it")
    email = auth.normalize_email(email)
    if not auth.is_valid_email(email):
        raise ValueError("Enter a valid email address")
    if not auth.MIN_PASSWORD_LENGTH <= len(password) <= auth.MAX_PASSWORD_LENGTH:
        raise ValueError(f"The password must be {auth.MIN_PASSWORD_LENGTH} to {auth.MAX_PASSWORD_LENGTH} characters")
    if session.scalar(select(Vendor.id).where(Vendor.email == email, Vendor.id != vendor.id)) is not None:
        raise ValueError("That email is already used by another vendor")
    vendor.email = email
    vendor.password_hash = auth.hash_password(password)
    session.commit()
    if replace:
        auth.end_all_sessions(session, vendor)
    return vendor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("business_name")
    parser.add_argument("email")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="change the email and password of a vendor that already has a login, and sign out its sessions",
    )
    args = parser.parse_args()
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Again: "):
        print("The passwords don't match.")
        return 1
    init_db()
    with SessionLocal() as session:
        try:
            vendor = claim(session, args.business_name, args.email, password, replace=args.replace)
        except ValueError as error:
            print(error)
            return 1
    print(f"{vendor.name} can now sign in as {vendor.email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
