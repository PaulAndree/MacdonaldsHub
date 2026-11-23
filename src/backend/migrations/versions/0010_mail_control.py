"""Control of the sender: global pause and the start of the last attempt.

Revision ID: 0010
Revises: 0009

One row. It starts paused, so a new environment sends nothing until the administrator resumes it.
Locking this row serializes the start of every attempt, and its last start time keeps the 30-second
interval global and across restarts.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mail_control",
        sa.Column("id", sa.SmallInteger(), primary_key=True, server_default="1"),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column("last_started_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("id = 1", name="ck_mail_control_single_row"),
    )
    op.execute("INSERT INTO mail_control (id, paused) VALUES (1, true)")
    # The consumer always takes the oldest pending email.
    op.create_index(
        "ix_outbox_pending_order",
        "outbox",
        ["created_at", "id"],
        postgresql_where=sa.text("state = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_pending_order", table_name="outbox")
    op.drop_table("mail_control")
