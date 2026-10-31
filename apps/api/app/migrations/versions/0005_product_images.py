"""Product pictures: a vendor uploads an image instead of pasting an address.

The bytes live in the database (free hosts lose their disk on every deploy). A product points at one with
image_url = "/product-images/<id>".

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_images",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vendor_id", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_images_vendor_id", "product_images", ["vendor_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_images_vendor_id", table_name="product_images")
    op.drop_table("product_images")
