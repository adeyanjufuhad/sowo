"""Product categories: a vendor groups products ("Shoes", "Bags") so the assistant can answer "which shoes?".

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("category", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_column("category")
