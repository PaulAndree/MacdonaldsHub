"""Batch rejection detail: what to tell the user about a rejected file (for example a header name).

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("batch", sa.Column("rejection_detail", sa.Text()))


def downgrade() -> None:
    op.drop_column("batch", "rejection_detail")
