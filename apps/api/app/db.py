from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(database_url: str) -> str:
    """Hosts hand out `postgres://` or `postgresql://`; SQLAlchemy needs the driver we ship (psycopg 3)."""
    for prefix in ("postgres://", "postgresql://"):
        if database_url.startswith(prefix):
            return "postgresql+psycopg://" + database_url[len(prefix) :]
    return database_url


def create_database_engine(database_url: str) -> Engine:
    database_url = normalize_database_url(database_url)
    if database_url.startswith("sqlite"):
        engine = create_engine(database_url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def enable_sqlite_wal(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    # pre_ping drops connections the database closed while the app was idle.
    return create_engine(database_url, pool_pre_ping=True)


engine = create_database_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def init_db() -> None:
    """Bring the database up to the latest schema. Safe to call on every start."""
    from app import models  # noqa: F401

    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables and tables:
            raise RuntimeError(
                "This database has tables but no migration history (it was made before Alembic). "
                "If its schema is current, run `alembic stamp head`; otherwise start from an empty database."
            )
        if connection.dialect.name == "postgresql":
            # Two replicas starting together must not both run the migrations; the lock ends with the transaction.
            connection.execute(text("SELECT pg_advisory_xact_lock(7403918)"))
        command.upgrade(alembic_config(connection), "head")


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
