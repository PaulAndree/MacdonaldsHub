"""Session-level PostgreSQL advisory lock that makes one worker the owner of the work loop.

The lock lives on a dedicated, long-lived connection. If that connection drops (crash,
restart, overlapping revision stopped) PostgreSQL releases the lock automatically.
"""

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError, OperationalError

# Fixed application-wide key for the worker loop (ADR-13).
WORKER_LOOP_KEY = 7_361_048_220_017


class AdvisoryLock:
    def __init__(self, engine: Engine, key: int = WORKER_LOOP_KEY) -> None:
        self._engine = engine
        self._key = key
        self._conn: Connection | None = None

    @property
    def held(self) -> bool:
        return self._conn is not None

    def backend_pid(self) -> int | None:
        if self._conn is None:
            return None
        return int(self._conn.execute(text("SELECT pg_backend_pid()")).scalar_one())

    def try_acquire(self) -> bool:
        """True when this instance now owns the lock. Never blocks."""
        if self._conn is not None:
            return self.still_held()
        conn = self._engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            got = bool(
                conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": self._key}).scalar_one()
            )
        except (OperationalError, DBAPIError):
            conn.close()
            raise
        if not got:
            conn.close()
            return False
        self._conn = conn
        return True

    def still_held(self) -> bool:
        """Verify the dedicated connection (and so the lock) is alive."""
        if self._conn is None:
            return False
        try:
            self._conn.execute(text("SELECT 1"))
            return True
        except (OperationalError, DBAPIError):
            self._drop()
            return False

    def release(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": self._key})
        except (OperationalError, DBAPIError):
            pass
        finally:
            self._drop()

    def _drop(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # connection may already be dead
                pass
            self._conn = None
