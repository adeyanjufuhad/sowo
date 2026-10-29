from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, create_database_engine
from app.models import Product
from app.seed import PRODUCTS, seed_data


def test_seed_creates_black_leather_loafers_with_exact_kobo_values(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_data(session)
        loafers = session.scalar(select(Product).where(Product.sku == "LOAF-BLK-43"))
    assert loafers is not None
    assert loafers.name == "Black Leather Loafers, size 43"
    assert loafers.price_kobo == 4500000
    assert loafers.floor_price_kobo == 4000000


def test_every_seeded_product_is_distinct_and_priced_above_its_floor(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_data(session)
        products = session.scalars(select(Product)).all()
        shea = session.scalar(select(Product).where(Product.sku == "SHEA-RAW-250"))
    assert len(products) == len(PRODUCTS)
    assert len({product.sku for product in products}) == len(PRODUCTS)
    assert all(0 < product.floor_price_kobo < product.price_kobo for product in products)
    # The demo shop is not only shoes.
    assert shea is not None and shea.name == "Raw Shea Butter, 250g"
