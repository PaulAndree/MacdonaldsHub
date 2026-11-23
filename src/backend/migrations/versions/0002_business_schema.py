"""Business schema: providers, branches, batches, staging, incidents, outbox, history, audit.

Revision ID: 0002
Revises: 0001

Rules the database itself guarantees (change 2):
- one incident per provider + Order ID (RN-01), whatever the batch or the concurrency;
- at most one unconfirmed batch per user (RF-17), also under simultaneous requests;
- one outbox record per incident;
- amounts are NUMERIC with no scale, so source digits are kept (RNF-13), and NULL means absent.
Branch values are NOT created here: the catalog comes from configuration (P-01).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.func.now()
BATCH_STATES = (
    "uploaded",
    "processing",
    "in_review",
    "rejected",
    "discarded",
    "confirmed",
    "completed",
)
INCIDENT_STATES = (
    "imported_no_email",
    "pending_send",
    "claimed",
    "send_error",
    "resolved",
    "rejected",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "provider",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        # Only Uber Eats and Just Eat create email; Glovo is tracked without it (RN-04).
        sa.Column("sends_email", sa.Boolean(), nullable=False),
        # Real recipients are unknown (P-01): configuration fills this, never a default here.
        sa.Column("recipient", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.bulk_insert(
        sa.table(
            "provider",
            sa.column("code", sa.Text),
            sa.column("display_name", sa.Text),
            sa.column("sends_email", sa.Boolean),
        ),
        [
            {"code": "uber eats", "display_name": "Uber Eats", "sends_email": True},
            {"code": "just eat", "display_name": "Just Eat", "sends_email": True},
            {"code": "glovo", "display_name": "Glovo", "sends_email": False},
        ],
    )
    op.create_table(
        "branch",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint("name = lower(name)", name="ck_branch_lowercase"),
    )

    op.create_table(
        "batch",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("blob_name", sa.Text(), nullable=False, unique=True),
        sa.Column("sha256", sa.Text()),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("identical_to_batch", UUID, sa.ForeignKey("batch.id")),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", sa.Text()),
        sa.Column("result", postgresql.JSONB()),
        sa.Column("original_copy", sa.Text()),
        sa.Column("cleanup", sa.Text(), nullable=False, server_default="none"),
        sa.Column("cleanup_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint(_in("state", BATCH_STATES), name="ck_batch_state"),
        sa.CheckConstraint(
            "original_copy IS NULL OR original_copy IN ('pending', 'verified', 'discrepancy')",
            name="ck_batch_original_copy",
        ),
        sa.CheckConstraint(
            "cleanup IN ('none', 'pending', 'done', 'failed')", name="ck_batch_cleanup"
        ),
    )
    # At most one unconfirmed batch per user (RF-17); rejected, discarded and confirmed ones
    # do not count.
    op.create_index(
        "uq_batch_one_unconfirmed",
        "batch",
        ["owner"],
        unique=True,
        postgresql_where=sa.text("state IN ('uploaded', 'processing', 'in_review')"),
    )

    op.create_table(
        "incident",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.Text(), sa.ForeignKey("provider.code"), nullable=False),
        # Alphanumeric text kept exactly as received: no trimming, no case change.
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        # Europe/Madrid wall-clock time, only when the source had one (never 00:00 by default).
        sa.Column("incident_time", sa.Time()),
        sa.Column("branch", sa.Text(), sa.ForeignKey("branch.name")),
        sa.Column("claim_amount", sa.Numeric()),
        sa.Column("provider_costs", sa.Numeric()),
        sa.Column("total", sa.Numeric()),
        sa.Column("description", sa.Text()),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("claim_date", sa.Date()),
        sa.Column("recovery_date", sa.Date()),
        sa.Column("recovered_amount", sa.Numeric()),
        sa.Column("batch_id", UUID, sa.ForeignKey("batch.id")),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("provider", "order_id", name="uq_incident_key"),
        sa.CheckConstraint(_in("state", INCIDENT_STATES), name="ck_incident_state"),
        sa.CheckConstraint("source IN ('import', 'manual')", name="ck_incident_source"),
    )
    op.create_index("ix_incident_incident_date", "incident", ["incident_date"])
    op.create_index("ix_incident_state", "incident", ["state"])

    op.create_table(
        "batch_row",
        sa.Column("batch_id", UUID, sa.ForeignKey("batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("class", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("provider", sa.Text()),
        sa.Column("order_id", sa.Text()),
        sa.Column("incident_date", sa.Date()),
        sa.Column("incident_time", sa.Time()),
        sa.Column("branch", sa.Text()),
        sa.Column("claim_amount", sa.Numeric()),
        sa.Column("provider_costs", sa.Numeric()),
        sa.Column("total", sa.Numeric()),
        sa.Column("description", sa.Text()),
        sa.Column("existing_incident_id", UUID, sa.ForeignKey("incident.id")),
        sa.PrimaryKeyConstraint("batch_id", "row_number"),
        sa.CheckConstraint(
            "class IN ('new', 'duplicate', 'conflict', 'error')", name="ck_batch_row_class"
        ),
    )

    op.create_table(
        "incident_history",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", UUID, sa.ForeignKey("incident.id"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("previous", sa.Text()),
        sa.Column("new", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("details", postgresql.JSONB()),
    )
    op.create_index("ix_incident_history_incident", "incident_history", ["incident_id", "at"])

    op.create_table(
        "outbox",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", UUID, sa.ForeignKey("incident.id"), nullable=False),
        sa.Column("batch_id", UUID, sa.ForeignKey("batch.id"), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        # The authorized version, copied at confirmation (RN-07); never a secret.
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("template_version", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("error_kind", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("incident_id", name="uq_outbox_incident"),
        sa.CheckConstraint(
            "state IN ('pending', 'sending', 'sent', 'error')", name="ck_outbox_state"
        ),
    )
    op.create_index("ix_outbox_state", "outbox", ["state"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_id", sa.Text()),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB()),
    )
    op.create_index("ix_audit_log_object", "audit_log", ["object_type", "object_id"])

    op.create_table(
        "setting",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )


def downgrade() -> None:
    for table in (
        "setting",
        "audit_log",
        "outbox",
        "incident_history",
        "batch_row",
        "incident",
        "batch",
        "branch",
        "provider",
    ):
        op.drop_table(table)
