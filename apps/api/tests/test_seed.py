from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, create_database_engine
from app.models import Product
from app.seed import seed_data


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
