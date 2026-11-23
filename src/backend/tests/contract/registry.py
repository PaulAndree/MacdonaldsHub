"""Which approved operations the API serves yet. Both lists shrink as the change advances.

`PENDING` holds operations a later phase of this change implements; the final check (task 7.4)
requires it to be empty. `DEFERRED` holds the operations that belong to change 3 and stay out of
this change on purpose (design D13). An operation in neither list must be served and must match.
"""

# Operation ids of docs/api/openapi.yaml still to implement in this change, with their phase.
PENDING: dict[str, int] = {}

# Change 3 (email-sending) serves the email queue.
DEFERRED: frozenset[str] = frozenset({"getEmailQueue", "pauseEmailQueue", "resumeEmailQueue"})

# Not part of the contract: platform-base technical operations without a user-facing screen.
NOT_IN_CONTRACT_PREFIXES: tuple[str, ...] = ("/api/technical", "/healthz", "/readyz")
