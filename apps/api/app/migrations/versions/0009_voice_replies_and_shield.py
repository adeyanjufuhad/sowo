"""Voice replies switch per vendor, and Scam Shield's flags.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vendors") as batch:
        batch.add_column(sa.Column("voice_replies", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_table(
        "shield_flags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=True),
        sa.Column("rule", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("evidence", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shield_flags_conversation_id", "shield_flags", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_shield_flags_conversation_id", table_name="shield_flags")
    op.drop_table("shield_flags")
    with op.batch_alter_table("vendors") as batch:
        batch.drop_column("voice_replies")
