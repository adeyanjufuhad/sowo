"""The signed-in vendor's own catalog: products and delivery zones.

The floor price is the vendor's secret. It is accepted and shown here, to the vendor only; nothing the model reads
(see services/catalog.py) ever carries it.
"""

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentVendor
from app.models import DeliveryZone, Offer, OrderItem, Product, StockHold, Vendor
from app.schemas import (
    DeleteProductResponse,
    DeliveryZoneCreate,
    DeliveryZoneEnvelope,
    DeliveryZoneResponse,
    DeliveryZoneUpdate,
    ListDeliveryZonesResponse,
    ProductCreate,
    ProductEnvelope,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db)]

SKU = re.compile(r"[A-Z0-9][A-Z0-9_.-]{0,63}")
MAX_PRICE_KOBO = 10_000_000_000  # ₦100,000,000
MAX_STOCK = 1_000_000
MAX_DELIVERY_FEE_KOBO = 50_000_000  # ₦500,000

SKU_TAKEN = "You already have a product with that sku (it may have been removed earlier)"
AREA_TAKEN = "You already deliver to that area"


def product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        sku=product.sku,
        name=product.name,
        basePriceKobo=product.price_kobo,
        floorPriceKobo=product.floor_price_kobo,
        stockOnHand=product.stock,
        imageUrl=product.image_url,
        description=product.description,
        size=product.size,
        colour=product.colour,
    )


def _bad(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def _clean(value: str | None, field: str, limit: int, *, required: bool = False) -> str:
    cleaned = " ".join((value or "").split())
    if required and not cleaned:
        raise _bad(f"{field} is required")
    if len(cleaned) > limit:
        raise _bad(f"{field} must be at most {limit} characters")
    return cleaned


def _sku(value: str | None) -> str:
    sku = (value or "").strip().upper()
    if not SKU.fullmatch(sku):
        raise _bad("The sku must be 1 to 64 letters, numbers, dots, dashes or underscores")
    return sku


def _image_url(value: str | None) -> str:
    url = (value or "").strip()
    if len(url) > 500:
        raise _bad("The image address must be at most 500 characters")
    if url and not re.match(r"https?://\S+$", url):
        raise _bad("The image address must start with http:// or https://")
    return url


def _check_prices(price: int, floor: int) -> None:
    if not 0 < price <= MAX_PRICE_KOBO:
        raise _bad("The price must be more than zero")
    if not 0 < floor <= price:
        raise _bad("The lowest price must be more than zero, and no more than the price")


def _check_stock(stock: int) -> None:
    if not 0 <= stock <= MAX_STOCK:
        raise _bad(f"Stock must be between 0 and {MAX_STOCK}")


def _owned_product(session: Session, vendor: Vendor, product_id: str) -> Product:
    product = session.get(Product, product_id)
    if product is None or product.vendor_id != vendor.id or product.archived_at is not None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product


def _sku_taken(session: Session, vendor: Vendor, sku: str, *, except_id: str | None = None) -> bool:
    found = session.scalar(
        select(Product.id).where(Product.vendor_id == vendor.id, Product.sku == sku, Product.id != (except_id or ""))
    )
    return found is not None


@router.post("/products", response_model=ProductEnvelope, status_code=201)
def create_product(payload: ProductCreate, session: SessionDependency, vendor: CurrentVendor) -> ProductEnvelope:
    sku = _sku(payload.sku)
    _check_prices(payload.basePriceKobo, payload.floorPriceKobo)
    _check_stock(payload.stockOnHand)
    if _sku_taken(session, vendor, sku):
        raise HTTPException(status_code=409, detail=SKU_TAKEN)
    product = Product(
        vendor_id=vendor.id,
        sku=sku,
        name=_clean(payload.name, "The name", 200, required=True),
        description=_clean(payload.description, "The description", 2000),
        size=_clean(payload.size, "The size", 32) or None,
        colour=_clean(payload.colour, "The colour", 64) or None,
        price_kobo=payload.basePriceKobo,
        floor_price_kobo=payload.floorPriceKobo,
        stock=payload.stockOnHand,
        image_url=_image_url(payload.imageUrl),
    )
    session.add(product)
    try:
        session.commit()
    except IntegrityError:  # the same sku was added a moment ago
        session.rollback()
        raise HTTPException(status_code=409, detail=SKU_TAKEN) from None
    return ProductEnvelope(product=product_response(product))


@router.patch("/products/{product_id}", response_model=ProductEnvelope)
def update_product(
    product_id: str, payload: ProductUpdate, session: SessionDependency, vendor: CurrentVendor
) -> ProductEnvelope:
    product = _owned_product(session, vendor, product_id)
    sent = payload.model_fields_set
    try:
        if "sku" in sent:
            sku = _sku(payload.sku)
            if sku != product.sku and _sku_taken(session, vendor, sku, except_id=product.id):
                raise HTTPException(status_code=409, detail=SKU_TAKEN)
            product.sku = sku
        if "name" in sent:
            product.name = _clean(payload.name, "The name", 200, required=True)
        if "description" in sent:
            product.description = _clean(payload.description, "The description", 2000)
        if "size" in sent:
            product.size = _clean(payload.size, "The size", 32) or None
        if "colour" in sent:
            product.colour = _clean(payload.colour, "The colour", 64) or None
        if "imageUrl" in sent:
            product.image_url = _image_url(payload.imageUrl)
        if "basePriceKobo" in sent and payload.basePriceKobo is not None:
            product.price_kobo = payload.basePriceKobo
        if "floorPriceKobo" in sent and payload.floorPriceKobo is not None:
            product.floor_price_kobo = payload.floorPriceKobo
        if "stockOnHand" in sent and payload.stockOnHand is not None:
            _check_stock(payload.stockOnHand)
            product.stock = payload.stockOnHand
        _check_prices(product.price_kobo, product.floor_price_kobo)  # the result must make sense, not just the input
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=SKU_TAKEN) from None
    return ProductEnvelope(product=product_response(product))


@router.delete("/products/{product_id}", response_model=DeleteProductResponse)
def delete_product(product_id: str, session: SessionDependency, vendor: CurrentVendor) -> DeleteProductResponse:
    """Delete a product nobody has touched. One that has been ordered, haggled over or held is archived instead, so
    the orders and chats that mention it keep working."""
    product = _owned_product(session, vendor, product_id)
    used = any(
        session.scalar(select(model.id).where(model.product_id == product.id).limit(1)) is not None
        for model in (OrderItem, Offer, StockHold)
    )
    if used:
        product.archived_at = datetime.now(UTC)
    else:
        session.delete(product)
    session.commit()
    return DeleteProductResponse(deleted=not used, archived=used)


# -- delivery zones ---------------------------------------------------------------------------------------


def _zone_response(zone: DeliveryZone) -> DeliveryZoneResponse:
    return DeliveryZoneResponse(id=zone.id, area=zone.area, feeKobo=zone.fee_kobo)


def _owned_zone(session: Session, vendor: Vendor, zone_id: str) -> DeliveryZone:
    zone = session.get(DeliveryZone, zone_id)
    if zone is None or zone.vendor_id != vendor.id:
        raise HTTPException(status_code=404, detail=f"Delivery zone {zone_id} not found")
    return zone


def _check_fee(fee: int) -> None:
    if not 0 <= fee <= MAX_DELIVERY_FEE_KOBO:
        raise _bad("The delivery fee must be between ₦0 and ₦500,000")


def _area_taken(session: Session, vendor: Vendor, area: str, *, except_id: str | None = None) -> bool:
    found = session.scalar(
        select(DeliveryZone.id).where(
            DeliveryZone.vendor_id == vendor.id,
            func.lower(DeliveryZone.area) == area.casefold(),
            DeliveryZone.id != (except_id or ""),
        )
    )
    return found is not None


@router.get("/delivery-zones", response_model=ListDeliveryZonesResponse)
def list_delivery_zones(session: SessionDependency, vendor: CurrentVendor) -> ListDeliveryZonesResponse:
    zones = session.scalars(
        select(DeliveryZone).where(DeliveryZone.vendor_id == vendor.id).order_by(DeliveryZone.area.asc())
    )
    return ListDeliveryZonesResponse(zones=[_zone_response(zone) for zone in zones])


@router.post("/delivery-zones", response_model=DeliveryZoneEnvelope, status_code=201)
def create_delivery_zone(
    payload: DeliveryZoneCreate, session: SessionDependency, vendor: CurrentVendor
) -> DeliveryZoneEnvelope:
    area = _clean(payload.area, "The area", 100, required=True)
    _check_fee(payload.feeKobo)
    if _area_taken(session, vendor, area):
        raise HTTPException(status_code=409, detail=AREA_TAKEN)
    zone = DeliveryZone(vendor_id=vendor.id, area=area, fee_kobo=payload.feeKobo)
    session.add(zone)
    session.commit()
    return DeliveryZoneEnvelope(zone=_zone_response(zone))


@router.patch("/delivery-zones/{zone_id}", response_model=DeliveryZoneEnvelope)
def update_delivery_zone(
    zone_id: str, payload: DeliveryZoneUpdate, session: SessionDependency, vendor: CurrentVendor
) -> DeliveryZoneEnvelope:
    zone = _owned_zone(session, vendor, zone_id)
    if payload.area is not None:
        area = _clean(payload.area, "The area", 100, required=True)
        if _area_taken(session, vendor, area, except_id=zone.id):
            raise HTTPException(status_code=409, detail=AREA_TAKEN)
        zone.area = area
    if payload.feeKobo is not None:
        _check_fee(payload.feeKobo)
        zone.fee_kobo = payload.feeKobo
    session.commit()
    return DeliveryZoneEnvelope(zone=_zone_response(zone))


@router.delete("/delivery-zones/{zone_id}", status_code=204)
def delete_delivery_zone(zone_id: str, session: SessionDependency, vendor: CurrentVendor) -> None:
    """Orders keep the area name they were placed with, so a zone can always be removed."""
    session.delete(_owned_zone(session, vendor, zone_id))
    session.commit()
