"""Audit trail is append-only: updates, deletes and truncation are refused (RF-19).

Revision ID: 0003
Revises: 0002

A trigger applies to every database role, including the application's, so the guarantee does not
depend on how the role was granted. Records can only be added.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION audit_log_refuse_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_log_no_row_change BEFORE UPDATE OR DELETE ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_refuse_change()"
    )
    op.execute(
        "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_refuse_change()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_log_no_truncate ON audit_log")
    op.execute("DROP TRIGGER audit_log_no_row_change ON audit_log")
    op.execute("DROP FUNCTION audit_log_refuse_change()")
