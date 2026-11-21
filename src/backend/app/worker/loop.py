"""Worker lifecycle: one owner of the loop at a time, a heartbeat, and no business work yet.

Importing (change 2) and email sending (change 3) plug into `work` later. In this change the
worker only demonstrates lifecycle and mutual exclusion.
"""

import json
import logging
import os
import tempfile
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from opentelemetry.trace import Tracer

from app.domain.clock import utc_now
from app.observability import log_event

State = Literal["starting", "standby", "owner", "stopped"]
LOG = logging.getLogger("app.worker")


class Lock(Protocol):
    def try_acquire(self) -> bool: ...
    def still_held(self) -> bool: ...
    def release(self) -> None: ...


class Worker:
    def __init__(
        self,
        lock: Lock,
        tracer: Tracer,
        heartbeat_path: Path,
        work: Callable[[], None] | None = None,
        instance_id: str | None = None,
    ) -> None:
        self._lock = lock
        self._tracer = tracer
        self._heartbeat_path = heartbeat_path
        self._work = work or (lambda: None)
        self.instance_id = instance_id or uuid.uuid4().hex[:12]
        self.state: State = "starting"

    def tick(self) -> State:
        """One loop iteration: (re)acquire or verify ownership, work only as owner, heartbeat."""
        with self._tracer.start_as_current_span("worker.tick") as span:
            try:
                owns = self._lock.still_held() or self._lock.try_acquire()
            except Exception as exc:  # database unreachable: not an owner
                owns = False
                log_event(
                    LOG, event="worker.error", instance=self.instance_id, error=type(exc).__name__
                )
            new_state: State = "owner" if owns else "standby"
            if new_state != self.state:
                self._transition(new_state)
            if owns:
                self._work()
            span.set_attribute("app.worker.instance", self.instance_id)
            span.set_attribute("app.worker.state", self.state)
            span.set_attribute("app.actor", "system:worker")
            span.set_attribute("app.result", "success")
        self._write_heartbeat()
        return self.state

    def run(self, stop: threading.Event, interval: float) -> None:
        try:
            while not stop.is_set():
                self.tick()
                stop.wait(interval)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._lock.release()
        self._transition("stopped")
        self._write_heartbeat()

    def _transition(self, new_state: State) -> None:
        previous, self.state = self.state, new_state
        log_event(
            LOG,
            event="worker.state",
            instance=self.instance_id,
            actor="system:worker",
            correlation_id=self.instance_id,
            previous=previous,
            state=new_state,
            result="success",
        )

    def _write_heartbeat(self) -> None:
        payload = {
            "instance": self.instance_id,
            "state": self.state,
            "updated_at": utc_now().isoformat(),
        }
        self._heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._heartbeat_path.parent)
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp, self._heartbeat_path)
