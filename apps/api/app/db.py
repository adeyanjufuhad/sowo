from collections.abc import Generator
from pathlib import Path
from typing import Any

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
    options: dict[str, Any] = {
        # Drop connections the database (or a pooler) closed while the app was idle, and retire old ones, because
        # a serverless Postgres such as Neon suspends after a few idle minutes.
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    if database_url.startswith("postgresql+psycopg"):
        # PgBouncer in transaction mode hands each transaction to a different server connection, so psycopg's
        # server-side prepared statements would collide. Never prepare them.
        options["connect_args"] = {"prepare_threshold": None}
    return create_engine(database_url, **options)


engine = create_database_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def init_db() -> None:
    """Bring the database up to the latest schema. Safe to call on every start."""
    from app import models  # noqa: F401

    settings = get_settings()
    # Migrations take the direct URL when there is one (a pooler in the middle is fine for the app, not for DDL).
    use_direct = bool(settings.database_url_direct) and engine.dialect.name != "sqlite"
    target = create_database_engine(settings.database_url_direct) if use_direct else engine
    try:
        _migrate(target)
    finally:
        if use_direct:
            target.dispose()


def _migrate(target: Engine) -> None:
    with target.begin() as connection:
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
