"""Staging keeps what each cell said, so an invalid row can be shown as the file had it.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("batch_row", sa.Column("raw", postgresql.JSONB()))
    op.create_index("ix_batch_row_key", "batch_row", ["batch_id", "provider", "order_id"])


def downgrade() -> None:
    op.drop_index("ix_batch_row_key", table_name="batch_row")
    op.drop_column("batch_row", "raw")
