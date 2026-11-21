"""Tiny HTTP health endpoint for orchestrator probes (Container Apps probes cannot run commands).

The worker still has no ingress: this port is only reachable by the platform's own probes.
It answers from the same heartbeat the loop writes, and exposes nothing else.
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.worker.healthcheck import MAX_AGE_SECONDS, is_healthy

HEALTH_PORT = 8081


def make_health_server(
    heartbeat: Path, port: int = HEALTH_PORT, max_age: float = MAX_AGE_SECONDS
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            healthy = self.path == "/healthz" and is_healthy(heartbeat, max_age)
            status = 200 if healthy else (404 if self.path != "/healthz" else 503)
            self.send_response(status)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n" if healthy else b"unavailable\n")

        def log_message(self, *args: object) -> None:
            pass

    return ThreadingHTTPServer(("0.0.0.0", port), Handler)  # noqa: S104


def serve_in_background(server: ThreadingHTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, name="worker-health", daemon=True)
    thread.start()
    return thread
