from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.models import DeliveryZone, Product, Vendor

PRODUCTS = [
    ("LOAF-BLK-43", "Black Leather Loafers, size 43", "Classic office loafers with cushioned insole.", "43", "Black", 4500000, 4000000, 3),
    ("LOAF-BRN-42", "Brown Leather Loafers, size 42", "Polished leather loafers for work and events.", "42", "Brown", 4300000, 3850000, 5),
    ("SNEAK-WHT-41", "White Everyday Sneakers, size 41", "Clean low-top sneakers for daily wear.", "41", "White", 3800000, 3350000, 8),
    ("SNEAK-BLK-44", "Black Street Sneakers, size 44", "Breathable black sneakers with rubber sole.", "44", "Black", 4000000, 3500000, 6),
    ("OXFORD-BLK-42", "Black Oxford Shoes, size 42", "Formal lace-up shoes for ceremonies and office days.", "42", "Black", 4800000, 4250000, 4),
    ("SANDAL-TAN-40", "Tan Leather Sandals, size 40", "Hand-finished open sandals for Lagos weather.", "40", "Tan", 2600000, 2300000, 10),
    ("SLIDE-BLU-43", "Navy Comfort Slides, size 43", "Soft-footbed slides for relaxed weekends.", "43", "Navy", 1800000, 1550000, 12),
    ("HEEL-RED-38", "Red Block Heels, size 38", "Stable block heels for parties and dinners.", "38", "Red", 3500000, 3050000, 5),
    ("PUMP-NUD-39", "Nude Court Pumps, size 39", "Versatile closed-toe pumps with a modest heel.", "39", "Nude", 3700000, 3250000, 4),
    ("FLAT-GLD-37", "Gold Ballet Flats, size 37", "Lightweight flats with a subtle metallic finish.", "37", "Gold", 2200000, 1900000, 9),
    ("BOOT-BLK-40", "Black Ankle Boots, size 40", "Durable ankle boots with side zip fastening.", "40", "Black", 5200000, 4650000, 3),
    ("MULE-CRM-38", "Cream Pointed Mules, size 38", "Easy slip-on mules for smart casual looks.", "38", "Cream", 2900000, 2500000, 7),
    ("KIDS-PNK-31", "Pink School Shoes, size 31", "Sturdy school shoes with secure buckle strap.", "31", "Pink", 1600000, 1400000, 11),
    ("KIDS-BLK-33", "Black School Shoes, size 33", "Polishable school shoes with non-slip sole.", "33", "Black", 1700000, 1450000, 10),
    ("TRAIN-GRY-42", "Grey Running Trainers, size 42", "Lightweight trainers for walks and gym sessions.", "42", "Grey", 4200000, 3700000, 6),
]
ZONES = [("Ikeja", 250000), ("Yaba", 200000), ("Lekki", 350000), ("Surulere", 220000), ("Victoria Island", 300000)]


def seed_data(session: Session) -> Vendor:
    vendor = session.scalar(select(Vendor).where(Vendor.name == "Ada's Footwear"))
    if vendor is None:
        vendor = Vendor(name="Ada's Footwear", owner_name="Ada")
        session.add(vendor)
        session.flush()
    for sku, name, description, size, colour, price, floor, stock in PRODUCTS:
        if session.scalar(select(Product).where(Product.vendor_id == vendor.id, Product.sku == sku)) is None:
            session.add(Product(vendor_id=vendor.id, sku=sku, name=name, description=description, size=size, colour=colour, price_kobo=price, floor_price_kobo=floor, stock=stock))
    for area, fee in ZONES:
        existing = session.scalar(select(DeliveryZone).where(DeliveryZone.vendor_id == vendor.id, DeliveryZone.area == area))
        if existing is None:
            session.add(DeliveryZone(vendor_id=vendor.id, area=area, fee_kobo=fee))
    session.commit()
    return vendor


def main() -> None:
    init_db()
    with SessionLocal() as session:
        seed_data(session)


if __name__ == "__main__":
    main()
