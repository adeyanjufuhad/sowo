"""Vendor accounts. The web app's server calls these and keeps the session token in its own httpOnly cookie."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import CurrentVendor, get_session_token
from app.models import Vendor
from app.ratelimit import LOGIN_FAILURE_WINDOW_SECONDS, limiter
from app.routes import _iso8601
from app.schemas import AuthResponse, LoginRequest, MeResponse, SignupRequest, VendorResponse
from app.services import auth

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db)]

BAD_LOGIN = "Incorrect email or password"


def _vendor_response(vendor: Vendor) -> VendorResponse:
    return VendorResponse(id=vendor.id, name=vendor.name, email=vendor.email)


def _signed_in(session: Session, vendor: Vendor) -> AuthResponse:
    token, expires_at = auth.create_session(session, vendor)
    return AuthResponse(vendor=_vendor_response(vendor), sessionToken=token, expiresAt=_iso8601(expires_at))


@router.post("/auth/signup", response_model=AuthResponse, status_code=201)
def signup(payload: SignupRequest, session: SessionDependency) -> AuthResponse:
    email = auth.normalize_email(payload.email)
    name = " ".join(payload.businessName.split())
    if not auth.is_valid_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if not 1 <= len(name) <= 120:
        raise HTTPException(status_code=400, detail="Enter your business name (up to 120 characters)")
    if len(payload.password) < auth.MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Use a password of at least {auth.MIN_PASSWORD_LENGTH} characters")
    if len(payload.password) > auth.MAX_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Use a password of at most {auth.MAX_PASSWORD_LENGTH} characters")
    if session.scalar(select(Vendor.id).where(Vendor.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    if session.scalar(select(Vendor.id).where(Vendor.name == name)) is not None:
        raise HTTPException(status_code=409, detail="A business with this name already exists")

    vendor = Vendor(name=name, email=email, password_hash=auth.hash_password(payload.password))
    session.add(vendor)
    try:
        session.commit()
    except IntegrityError:  # someone signed up with the same email or name a moment ago
        session.rollback()
        raise HTTPException(status_code=409, detail="That email or business name is already taken") from None
    return _signed_in(session, vendor)


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, session: SessionDependency) -> AuthResponse:
    email = auth.normalize_email(payload.email)
    settings = get_settings()
    # Guessing one account's password from many addresses gets past the per-address limit, so failures are also
    # counted per email. The key is the email as typed (even if no such account exists), so this doesn't reveal
    # which emails have accounts.
    failures_key = f"login-failures:{email[:254]}"
    if settings.rate_limit_enabled:
        wait = limiter.retry_after(failures_key, settings.login_max_failures, LOGIN_FAILURE_WINDOW_SECONDS)
        if wait:
            raise HTTPException(
                status_code=429,
                detail="Too many failed sign-in attempts. Wait a few minutes and try again.",
                headers={"Retry-After": str(max(1, int(wait)))},
            )
    vendor = session.scalar(select(Vendor).where(Vendor.email == email))
    if not auth.check_password(vendor, payload.password) or vendor is None:
        limiter.record(failures_key, LOGIN_FAILURE_WINDOW_SECONDS)
        raise HTTPException(status_code=401, detail=BAD_LOGIN)
    limiter.clear(failures_key)
    session.commit()  # keeps a rehashed password, if the hash parameters were raised
    return _signed_in(session, vendor)


@router.post("/auth/logout")
def logout(
    _: CurrentVendor, token: Annotated[str, Depends(get_session_token)], session: SessionDependency
) -> dict[str, bool]:
    auth.end_session(session, token)
    return {"ok": True}


@router.get("/auth/me", response_model=MeResponse)
def me(vendor: CurrentVendor) -> MeResponse:
    return MeResponse(vendor=_vendor_response(vendor))
