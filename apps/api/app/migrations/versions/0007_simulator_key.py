"""Remember which shop the /try demo talks to, so the shop can change its name without the demo losing it.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vendors") as batch:
        batch.add_column(sa.Column("simulator_key", sa.String(length=120), nullable=True))
        batch.create_unique_constraint("uq_vendors_simulator_key", ["simulator_key"])


def downgrade() -> None:
    with op.batch_alter_table("vendors") as batch:
        batch.drop_constraint("uq_vendors_simulator_key", type_="unique")
        batch.drop_column("simulator_key")
