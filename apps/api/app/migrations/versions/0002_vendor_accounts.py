"""Vendor accounts: login columns, dashboard sessions, and every conversation belongs to a vendor.

Existing conversations are given to the first vendor (by name). If there are conversations but no vendor at
all, a placeholder vendor is created to own them, so the NOT NULL column can be added.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vendors") as batch:
        batch.add_column(sa.Column("email", sa.String(length=254), nullable=True))
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )
        batch.create_unique_constraint("uq_vendors_email", ["email"])

    op.create_table(
        "vendor_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vendor_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_vendor_sessions_vendor_id", "vendor_sessions", ["vendor_id"], unique=False)

    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("vendor_id", sa.String(length=36), nullable=True))

    # Plain SQL (no Python branching) so `alembic upgrade --sql` can print it too.
    op.execute(
        f"INSERT INTO vendors (id, name) SELECT '{uuid.uuid4()}', 'My shop' "
        "WHERE NOT EXISTS (SELECT 1 FROM vendors) AND EXISTS (SELECT 1 FROM conversations)"
    )
    op.execute(
        "UPDATE conversations SET vendor_id = (SELECT id FROM vendors ORDER BY name LIMIT 1) "
        "WHERE vendor_id IS NULL"
    )

    with op.batch_alter_table("conversations") as batch:
        batch.alter_column("vendor_id", existing_type=sa.String(length=36), nullable=False)
        batch.create_foreign_key("fk_conversations_vendor_id_vendors", "vendors", ["vendor_id"], ["id"])
        batch.create_index("ix_conversations_vendor_id", ["vendor_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.drop_index("ix_conversations_vendor_id")
        batch.drop_constraint("fk_conversations_vendor_id_vendors", type_="foreignkey")
        batch.drop_column("vendor_id")
    op.drop_index("ix_vendor_sessions_vendor_id", table_name="vendor_sessions")
    op.drop_table("vendor_sessions")
    with op.batch_alter_table("vendors") as batch:
        batch.drop_constraint("uq_vendors_email", type_="unique")
        batch.drop_column("created_at")
        batch.drop_column("password_hash")
        batch.drop_column("email")
