"""History entries written together keep the order they were written in.

Revision ID: 0009
Revises: 0008

Several entries of one change share the instant of their transaction, so ordering by time alone
left them in an arbitrary order. A sequence number settles it.
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incident_history",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("incident_history", "seq")
