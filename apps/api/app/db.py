from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def enable_sqlite_wal(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = create_database_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        _add_sqlite_columns_if_missing()


def _add_sqlite_columns_if_missing() -> None:
    """Apply the small additive schema changes needed by the local Stage 1 database."""
    additions = {
        "products": {"image_url": "VARCHAR(500) NOT NULL DEFAULT ''"},
        "conversations": {"customer_name": "VARCHAR(120) NOT NULL DEFAULT ''"},
        "orders": {"delivery_area": "VARCHAR(100)", "created_at": "DATETIME"},
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
