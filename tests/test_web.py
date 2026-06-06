"""Tests for brainstorm_tool.web."""

from __future__ import annotations

from http.client import HTTPConnection
import json
from pathlib import Path
import threading

from brainstorm_tool.web import ThreadingTCPServer, make_handler


def test_make_handler_sets_api_and_static_dir(tmp_path: Path) -> None:
    handler = make_handler(tmp_path / "brainstorm.db")

    assert handler.static_dir.name == "static"
    assert handler.api.store.db_path == tmp_path / "brainstorm.db"


def test_server_serves_static_and_api(tmp_path: Path) -> None:
    handler = make_handler(tmp_path / "brainstorm.db")
    server = ThreadingTCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    connection: HTTPConnection | None = None
    thread.start()
    try:
        host, port = server.server_address
        connection = HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/preview.html")
        html = connection.getresponse().read().decode("utf-8")
        connection.request("GET", "/api/ideas")
        ideas = json.loads(connection.getresponse().read().decode("utf-8"))
    finally:
        if connection is not None:
            connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "Brainstorm Dashboard Preview" in html
    assert ideas == {"ideas": []}


def test_server_accepts_json_post(tmp_path: Path) -> None:
    handler = make_handler(tmp_path / "brainstorm.db")
    server = ThreadingTCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    connection: HTTPConnection | None = None
    thread.start()
    try:
        host, port = server.server_address
        connection = HTTPConnection(host, port, timeout=5)
        connection.request(
            "POST",
            "/api/ideas",
            body=json.dumps(
                {
                    "title": "HTTP idea",
                    "brief": "Created through HTTP.",
                    "content": "Body",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        created = json.loads(connection.getresponse().read().decode("utf-8"))
    finally:
        if connection is not None:
            connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert created["title"] == "HTTP idea"


def test_server_serves_draft_inbox_and_api(tmp_path: Path) -> None:
    handler = make_handler(tmp_path / "brainstorm.db")
    server = ThreadingTCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    connection: HTTPConnection | None = None
    thread.start()
    try:
        host, port = server.server_address
        connection = HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/")
        html = connection.getresponse().read().decode("utf-8")
        connection.request(
            "POST",
            "/api/drafts",
            body=json.dumps(
                {
                    "raw_message": "add a new idea: HTTP draft",
                    "source": "dashboard",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        draft = json.loads(connection.getresponse().read().decode("utf-8"))
    finally:
        if connection is not None:
            connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "quickCaptureForm" in html
    assert "draftInbox" in html
    assert draft["draft_id"] == 1
