import json
import logging
import os
import threading
import time
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.worker.healthcheck import is_healthy
from app.worker.loop import Worker


class FakeLock:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.held = False
        self.released = 0

    def try_acquire(self) -> bool:
        self.held = self.available
        return self.held

    def still_held(self) -> bool:
        return self.held

    def release(self) -> None:
        self.held = False
        self.released += 1


def tracer_and_exporter() -> tuple[object, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


def make(tmp_path: Path, lock: FakeLock, work=None) -> tuple[Worker, InMemorySpanExporter]:  # type: ignore[no-untyped-def]
    tracer, exporter = tracer_and_exporter()
    return Worker(lock, tracer, tmp_path / "hb.json", work, instance_id="w1"), exporter  # type: ignore[arg-type]


def test_owner_runs_work_and_standby_does_not(tmp_path: Path) -> None:
    calls: list[int] = []
    owner, _ = make(tmp_path / "a", FakeLock(True), lambda: calls.append(1))
    standby, _ = make(tmp_path / "b", FakeLock(False), lambda: calls.append(2))
    assert owner.tick() == "owner"
    assert standby.tick() == "standby"
    assert calls == [1]


def test_standby_takes_over_when_lock_becomes_available(tmp_path: Path) -> None:
    lock = FakeLock(False)
    worker, _ = make(tmp_path, lock)
    assert worker.tick() == "standby"
    lock.available = True
    assert worker.tick() == "owner"


def test_owner_that_loses_connection_becomes_standby(tmp_path: Path) -> None:
    lock = FakeLock(True)
    ran: list[int] = []
    worker, _ = make(tmp_path, lock, lambda: ran.append(1))
    assert worker.tick() == "owner"
    lock.held = False
    lock.available = False
    assert worker.tick() == "standby"
    assert ran == [1]


def test_lock_errors_do_not_crash_the_loop(tmp_path: Path) -> None:
    class Broken(FakeLock):
        def try_acquire(self) -> bool:
            raise ConnectionError("db down")

    worker, _ = make(tmp_path, Broken())
    assert worker.tick() == "standby"


def test_heartbeat_file_reports_state(tmp_path: Path) -> None:
    worker, _ = make(tmp_path, FakeLock(True))
    worker.tick()
    data = json.loads((tmp_path / "hb.json").read_text())
    assert data["state"] == "owner" and data["instance"] == "w1" and data["updated_at"]
    assert is_healthy(tmp_path / "hb.json")


def test_shutdown_releases_lock_and_reports_stopped(tmp_path: Path) -> None:
    lock = FakeLock(True)
    worker, _ = make(tmp_path, lock)
    stop = threading.Event()
    stop.set()
    worker.run(stop, 0.01)
    assert lock.released == 1
    assert json.loads((tmp_path / "hb.json").read_text())["state"] == "stopped"
    assert not is_healthy(tmp_path / "hb.json")


def test_lifecycle_telemetry_has_actor_correlation_and_result(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    worker, exporter = make(tmp_path, FakeLock(True))
    with caplog.at_level(logging.INFO, logger="app.worker"):
        worker.tick()
    event = json.loads(next(r for r in caplog.records if r.name == "app.worker").getMessage())
    assert event["event"] == "worker.state" and event["state"] == "owner"
    assert event["actor"] == "system:worker" and event["correlation_id"] == "w1"
    assert event["result"] == "success"
    attrs = exporter.get_finished_spans()[-1].attributes
    assert attrs["app.worker.state"] == "owner" and attrs["app.actor"] == "system:worker"  # type: ignore[index]


def test_healthcheck_rejects_missing_stale_and_garbage(tmp_path: Path) -> None:
    path = tmp_path / "hb.json"
    assert not is_healthy(path)
    path.write_text("not json")
    assert not is_healthy(path)
    path.write_text(json.dumps({"state": "owner"}))
    old = time.time() - 600
    os.utime(path, (old, old))
    assert not is_healthy(path, max_age=60)
    os.utime(path, None)
    assert is_healthy(path, max_age=60)
