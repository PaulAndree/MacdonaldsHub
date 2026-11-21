"""Tiny upstream that echoes the request line and headers it received as JSON."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _reply(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        payload = json.dumps(
            {
                "path": self.path,
                "host": self.headers.get("Host"),
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": body,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = _reply

    def log_message(self, *args: object) -> None:
        pass


HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
