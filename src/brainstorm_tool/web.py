"""Browser dashboard server for the brainstorm workspace."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
import mimetypes
from pathlib import Path
from socketserver import TCPServer
from typing import TypeAlias, cast
from urllib.parse import urlparse

from brainstorm_tool.api import ApiApp
from brainstorm_tool.store import BrainstormStore

JsonPayload: TypeAlias = dict[str, object] | None


class ThreadingTCPServer(TCPServer):
    """TCP server configured for quick local restarts."""

    allow_reuse_address = True


class DashboardHandler(BaseHTTPRequestHandler):
    """Serve static dashboard assets and JSON API requests."""

    api: ApiApp
    static_dir: Path

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests."""
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self._send_api("GET", None)
            return
        self._send_static(path)

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST requests."""
        self._send_api("POST", self._read_json())

    def do_DELETE(self) -> None:  # noqa: N802
        """Handle DELETE requests."""
        self._send_api("DELETE", self._read_json())

    def log_message(self, format: str, *args: object) -> None:
        """Log requests through the default server format."""
        super().log_message(format, *args)

    def _send_api(self, method: str, payload: JsonPayload) -> None:
        response = self.api.dispatch(method, urlparse(self.path).path, payload)
        body = json.dumps(response.body).encode("utf-8")
        self.send_response(response.status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if response.status_code != 204:
            self.wfile.write(body)

    def _send_static(self, path: str) -> None:
        requested = "index.html" if path in {"/", ""} else path.lstrip("/")
        static_path = (self.static_dir / requested).resolve()
        if not str(static_path).startswith(str(self.static_dir.resolve())):
            self.send_error(403)
            return
        if not static_path.exists() or static_path.is_dir():
            static_path = self.static_dir / "index.html"
        content = static_path.read_bytes()
        content_type = mimetypes.guess_type(static_path.name)[0] or "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self) -> JsonPayload:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return None
        body = self.rfile.read(content_length).decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            return None
        return parsed


def serve(db_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the browser dashboard server.

    Args:
        db_path: SQLite database path.
        host: Bind host for the server.
        port: Bind port for the server.
    """
    handler = make_handler(db_path)
    with ThreadingTCPServer((host, port), handler) as httpd:
        print(f"Brainstorm dashboard: http://{host}:{port}")
        httpd.serve_forever()


def make_handler(db_path: Path) -> type[DashboardHandler]:
    """Create a configured dashboard request handler class.

    Args:
        db_path: SQLite database path for API requests.

    Returns:
        Handler class with API and static directory configured.
    """

    class ConfiguredDashboardHandler(DashboardHandler):
        api = ApiApp(BrainstormStore(db_path))
        static_dir = Path(__file__).parent / "static"

    return cast(type[DashboardHandler], ConfiguredDashboardHandler)
