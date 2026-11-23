"""An outbox record can belong to a manual entry, which has no batch.

Revision ID: 0008
Revises: 0007
"""

from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "outbox", "batch_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True
    )


def downgrade() -> None:
    # Records of manual entries have no batch, so they cannot stay when a batch is mandatory again.
    op.execute("DELETE FROM outbox WHERE batch_id IS NULL")
    op.alter_column(
        "outbox", "batch_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False
    )
