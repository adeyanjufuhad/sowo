"""The signed-in vendor's own setup: the WhatsApp number buyers message, where alerts go, how buyers pay."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import CurrentVendor
from app.models import Vendor
from app.schemas import VendorSettingsResponse, VendorSettingsUpdate
from app.services.vendors import BANK_ACCOUNT_NUMBER, vendor_bank

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db)]

PHONE_NUMBER_ID = re.compile(r"\d{5,32}")


def settings_response(vendor: Vendor) -> VendorSettingsResponse:
    return VendorSettingsResponse(
        businessName=vendor.name,
        ownerName=vendor.owner_name,
        whatsappPhoneNumberId=vendor.whatsapp_phone_number_id,
        alertPhone=vendor.alert_phone,
        paymentMode="manual" if vendor.payment_mode == "manual" else "paystack",
        bankName=vendor.bank_name,
        bankAccountName=vendor.bank_account_name,
        bankAccountNumber=vendor.bank_account_number,
        paymentReady=vendor.payment_mode != "manual" or vendor_bank(vendor) is not None,
        whatsappConnected=bool(vendor.whatsapp_phone_number_id and get_settings().whatsapp_access_token),
    )


def _text(value: str | None, field: str, limit: int) -> str | None:
    cleaned = " ".join((value or "").split())
    if len(cleaned) > limit:
        raise HTTPException(status_code=400, detail=f"{field} must be at most {limit} characters")
    return cleaned or None


def _digits(value: str | None, field: str, pattern: re.Pattern[str]) -> str | None:
    cleaned = re.sub(r"[\s\-+()]", "", value or "")
    if not cleaned:
        return None
    if not pattern.fullmatch(cleaned):
        raise HTTPException(status_code=400, detail=f"{field} is not valid")
    return cleaned


@router.get("/vendor/settings", response_model=VendorSettingsResponse)
def get_vendor_settings(vendor: CurrentVendor) -> VendorSettingsResponse:
    return settings_response(vendor)


@router.patch("/vendor/settings", response_model=VendorSettingsResponse)
def update_vendor_settings(
    payload: VendorSettingsUpdate, session: SessionDependency, vendor: CurrentVendor
) -> VendorSettingsResponse:
    sent = payload.model_fields_set
    if "ownerName" in sent:
        vendor.owner_name = _text(payload.ownerName, "The owner's name", 80)
    if "whatsappPhoneNumberId" in sent:
        vendor.whatsapp_phone_number_id = _digits(payload.whatsappPhoneNumberId, "The WhatsApp phone number ID", PHONE_NUMBER_ID)
    if "alertPhone" in sent:
        vendor.alert_phone = _digits(payload.alertPhone, "The alert phone number", re.compile(r"\d{7,15}"))
    if "bankName" in sent:
        vendor.bank_name = _text(payload.bankName, "The bank name", 80)
    if "bankAccountName" in sent:
        vendor.bank_account_name = _text(payload.bankAccountName, "The account name", 120)
    if "bankAccountNumber" in sent:
        vendor.bank_account_number = _digits(payload.bankAccountNumber, "The account number", BANK_ACCOUNT_NUMBER)
    if "paymentMode" in sent and payload.paymentMode is not None:
        vendor.payment_mode = payload.paymentMode
    if vendor.payment_mode == "manual" and vendor_bank(vendor) is None:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Bank transfer needs a bank name, an account name and a 10-digit account number",
        )
    taken = vendor.whatsapp_phone_number_id and session.scalar(
        select(Vendor.id).where(Vendor.whatsapp_phone_number_id == vendor.whatsapp_phone_number_id, Vendor.id != vendor.id)
    )
    if taken:
        session.rollback()
        raise HTTPException(status_code=409, detail="That WhatsApp number is already connected to another shop")
    try:
        session.commit()
    except IntegrityError:  # the same number was claimed a moment ago
        session.rollback()
        raise HTTPException(status_code=409, detail="That WhatsApp number is already connected to another shop") from None
    return settings_response(vendor)
