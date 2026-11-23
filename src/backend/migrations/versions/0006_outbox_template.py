"""The outbox keeps the authorized subject and body, so editing the template later changes nothing.

Revision ID: 0006
Revises: 0005

The text has {orderId} as its only variable and never holds a secret. No outbox row exists before
change 2 confirms its first batch, so the columns can be mandatory.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outbox", sa.Column("subject", sa.Text(), nullable=False))
    op.add_column("outbox", sa.Column("body", sa.Text(), nullable=False))


def downgrade() -> None:
    op.drop_column("outbox", "body")
    op.drop_column("outbox", "subject")
