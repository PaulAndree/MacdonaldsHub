"""PostgreSQL audit log. It writes with the caller's connection, so the record belongs to the same
transaction as the change it describes: both exist or neither does (RF-08)."""

from sqlalchemy import Connection, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import bindparam

from app.services.ports import AuditEntry

_INSERT = text(
    "INSERT INTO audit_log (at, actor, operation, object_type, object_id, outcome, details) "
    "VALUES (:at, :actor, :operation, :object_type, :object_id, :outcome, :details)"
).bindparams(bindparam("details", type_=JSONB))


class SqlAuditLog:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def record(self, entry: AuditEntry) -> None:
        self._connection.execute(
            _INSERT,
            {
                "at": entry.at,
                "actor": entry.actor,
                "operation": entry.operation,
                "object_type": entry.object_type,
                "object_id": entry.object_id,
                "outcome": entry.outcome,
                "details": entry.details,
            },
        )
