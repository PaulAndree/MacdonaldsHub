import json
import os
import time
from pathlib import Path

import httpx

from app.worker.health_server import make_health_server, serve_in_background


def start(path: Path, max_age: float = 60.0):  # type: ignore[no-untyped-def]
    server = make_health_server(path, port=0, max_age=max_age)
    serve_in_background(server)
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_healthy_only_with_a_fresh_heartbeat(tmp_path: Path) -> None:
    hb = tmp_path / "hb.json"
    server, base = start(hb)
    try:
        assert httpx.get(f"{base}/healthz").status_code == 503  # no heartbeat yet
        hb.write_text(json.dumps({"state": "standby"}))
        assert httpx.get(f"{base}/healthz").status_code == 200
        old = time.time() - 600
        os.utime(hb, (old, old))
        assert httpx.get(f"{base}/healthz").status_code == 503  # stale
        hb.write_text(json.dumps({"state": "stopped"}))
        assert httpx.get(f"{base}/healthz").status_code == 503
    finally:
        server.shutdown()


def test_exposes_nothing_but_healthz(tmp_path: Path) -> None:
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps({"state": "owner"}))
    server, base = start(hb)
    try:
        assert httpx.get(f"{base}/").status_code == 404
        assert httpx.get(f"{base}/metrics").status_code == 404
        assert httpx.post(f"{base}/healthz").status_code == 501
    finally:
        server.shutdown()
