"""The schema comes from Alembic migrations, and the migrations must always match the models."""

from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

import app.db as database
from app.config import get_settings
from app.db import Base, alembic_config, create_database_engine, normalize_database_url


@pytest.fixture
def engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'm.db'}")
    monkeypatch.setattr(database, "engine", engine)
    yield engine
    engine.dispose()


def test_a_fresh_database_gets_the_full_schema(engine) -> None:
    database.init_db()

    tables = set(inspect(engine).get_table_names())
    assert tables == set(Base.metadata.tables) | {"alembic_version"}


def test_migrations_match_the_models(engine) -> None:
    """If a model changes without a migration, this fails: that would break every real database."""
    database.init_db()

    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_starting_twice_is_harmless(engine) -> None:
    database.init_db()
    database.init_db()

    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1


def test_a_database_from_before_alembic_is_refused_with_a_clear_message(engine) -> None:
    Base.metadata.create_all(engine)  # how databases used to be made

    with pytest.raises(RuntimeError, match="alembic stamp head"):
        database.init_db()


def test_every_migration_can_be_undone(engine) -> None:
    database.init_db()
    with engine.begin() as connection:
        command.downgrade(alembic_config(connection), "base")

    assert set(inspect(engine).get_table_names()) == {"alembic_version"}


def test_the_postgres_schema_creates_its_enum_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Postgres server is needed: Alembic can print the SQL it would run."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@db:5432/sowo")
    get_settings.cache_clear()
    out = StringIO()
    config = alembic_config()
    config.output_buffer = out
    try:
        command.upgrade(config, "head", sql=True)
    finally:
        get_settings.cache_clear()

    sql = out.getvalue()
    assert "CREATE TYPE paymentmethod AS ENUM ('PAYSTACK', 'MANUAL')" in sql
    assert "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL" in sql
    assert "CREATE TABLE stock_holds" in sql


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgresql://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("postgresql+psycopg://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("sqlite:///./sowo.db", "sqlite:///./sowo.db"),
    ],
)
def test_database_urls_are_pointed_at_the_installed_driver(given: str, expected: str) -> None:
    assert normalize_database_url(given) == expected


def _insert_old_data(engine, *, with_vendor: bool) -> None:
    """A database as it was at migration 0001: conversations, and (maybe) a vendor, but no vendor_id column yet."""
    with engine.begin() as connection:
        if with_vendor:
            connection.execute(text("INSERT INTO vendors (id, name) VALUES ('v-ada', 'Ada''s Footwear')"))
        connection.execute(
            text(
                "INSERT INTO conversations (id, customer_phone, customer_name, status, ai_paused, greeted, is_simulator) "
                "VALUES ('c1', '2348012345678', 'Funke', 'ACTIVE', 0, 0, 0)"
            )
        )


def test_existing_conversations_are_given_to_the_first_vendor(engine) -> None:
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "0001")
    _insert_old_data(engine, with_vendor=True)

    database.init_db()

    with engine.connect() as connection:
        assert connection.execute(text("SELECT vendor_id FROM conversations")).scalar_one() == "v-ada"


def test_conversations_with_no_vendor_get_a_placeholder_owner(engine) -> None:
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), "0001")
    _insert_old_data(engine, with_vendor=False)

    database.init_db()

    with engine.connect() as connection:
        owner = connection.execute(text("SELECT vendor_id FROM conversations")).scalar_one()
        assert connection.execute(text("SELECT name FROM vendors WHERE id = :id"), {"id": owner}).scalar_one() == "My shop"
