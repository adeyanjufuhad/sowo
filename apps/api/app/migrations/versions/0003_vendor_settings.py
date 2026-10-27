"""Per-vendor settings, and SKUs that only have to be unique within one vendor's catalog.

Moves what used to be environment variables (WhatsApp number, alert phone, payment mode, bank details) onto the
vendor's row so several vendors can share one deployment. Nothing is copied from the environment: set each
vendor's values through the dashboard API (PATCH /vendor/settings) after upgrading.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Lets SQLite's table rebuild name the unnamed UNIQUE(sku) that revision 0001 created, so it can be dropped.
NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _old_sku_constraint(dialect: str) -> str:
    """The name of the UNIQUE(sku) constraint 0001 created. Postgres named it itself; SQLite didn't."""
    if dialect == "sqlite":
        return "uq_products_sku"  # the name NAMING gives it while the table is rebuilt
    name = "products_sku_key"  # Postgres' default, which is also what an offline --sql run assumes
    if not op.get_context().as_sql:
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("products"):
            if constraint["column_names"] == ["sku"]:
                name = constraint["name"] or name
    return name


def upgrade() -> None:
    with op.batch_alter_table("vendors") as batch:
        batch.add_column(sa.Column("owner_name", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("whatsapp_phone_number_id", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("alert_phone", sa.String(length=32), nullable=True))
        batch.add_column(
            sa.Column("payment_mode", sa.String(length=16), server_default="paystack", nullable=False)
        )
        batch.add_column(sa.Column("bank_name", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("bank_account_name", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("bank_account_number", sa.String(length=10), nullable=True))
        batch.create_unique_constraint("uq_vendors_whatsapp_phone_number_id", ["whatsapp_phone_number_id"])

    dialect = op.get_context().dialect.name
    with op.batch_alter_table("products", naming_convention=NAMING) as batch:
        batch.drop_constraint(_old_sku_constraint(dialect), type_="unique")
        batch.create_unique_constraint("uq_products_vendor_id_sku", ["vendor_id", "sku"])


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("uq_products_vendor_id_sku", type_="unique")
        batch.create_unique_constraint("uq_products_sku", ["sku"])

    with op.batch_alter_table("vendors") as batch:
        batch.drop_constraint("uq_vendors_whatsapp_phone_number_id", type_="unique")
        batch.drop_column("bank_account_number")
        batch.drop_column("bank_account_name")
        batch.drop_column("bank_name")
        batch.drop_column("payment_mode")
        batch.drop_column("alert_phone")
        batch.drop_column("whatsapp_phone_number_id")
        batch.drop_column("owner_name")
