"""Buyers' voice notes: the audio, and the transcript's place on the message.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_notes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voice_notes_conversation_id", "voice_notes", ["conversation_id"])
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("kind", sa.String(length=16), server_default="text", nullable=False))
        batch.add_column(sa.Column("voice_status", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("voice_note_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_messages_voice_note_id_voice_notes", "voice_notes", ["voice_note_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("fk_messages_voice_note_id_voice_notes", type_="foreignkey")
        batch.drop_column("voice_note_id")
        batch.drop_column("voice_status")
        batch.drop_column("kind")
    op.drop_index("ix_voice_notes_conversation_id", table_name="voice_notes")
    op.drop_table("voice_notes")
