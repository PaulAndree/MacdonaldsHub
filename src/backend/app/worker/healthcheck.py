"""Container health command: `python -m app.worker.healthcheck`. Exit 0 when the heartbeat is fresh.

The worker has no HTTP ingress, so liveness is a recently written heartbeat file.
"""

import json
import sys
import time
from pathlib import Path

DEFAULT_PATH = Path("/tmp/worker-heartbeat.json")  # noqa: S108
MAX_AGE_SECONDS = 60.0


def is_healthy(path: Path, max_age: float = MAX_AGE_SECONDS, now: float | None = None) -> bool:
    try:
        data = json.loads(path.read_text())
        age = (now if now is not None else time.time()) - path.stat().st_mtime
    except (OSError, ValueError):
        return False
    return data.get("state") in ("owner", "standby") and age <= max_age


def main() -> None:
    sys.exit(0 if is_healthy(DEFAULT_PATH) else 1)


if __name__ == "__main__":
    main()
