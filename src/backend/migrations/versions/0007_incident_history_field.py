"""History entries say which value changed (status, claim date, recovered amount...).

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incident_history", sa.Column("field", sa.Text(), nullable=False, server_default="status")
    )
    op.create_check_constraint(
        "ck_incident_history_field",
        "incident_history",
        "field IN ('status', 'claimDate', 'result', 'recoveredAmount', 'recoveryDate')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_incident_history_field", "incident_history", type_="check")
    op.drop_column("incident_history", "field")
