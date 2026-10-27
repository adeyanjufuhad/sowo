"""Alembic environment. The database comes from the app's settings, or from a connection the caller passes in."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.config import get_settings
from app.db import Base, create_database_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def migration_url() -> str:
    settings = get_settings()
    return settings.database_url_direct or settings.database_url


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite can't ALTER most things in place; batch mode rebuilds the table instead.
        render_as_batch=connection.dialect.name == "sqlite",
    )


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL for a database instead of running it."""
    context.configure(
        url=migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    # SQLite rebuilds a table to change it (copy, drop, rename). With foreign keys enforced, dropping a table that
    # other tables point at fails, so they are switched off for the migration, as SQLite's own docs advise.
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        _configure(connection)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # the app runs migrations on its own engine at startup
        _run(connection)
        return

    engine = create_database_engine(migration_url())
    with engine.connect() as connection:
        _run(connection)
        connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
