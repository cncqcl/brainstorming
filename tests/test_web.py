"""Tests for brainstorm_tool.web."""

from __future__ import annotations

from pathlib import Path

from brainstorm_tool.web import make_handler


def test_make_handler_sets_api_and_static_dir(tmp_path: Path) -> None:
    handler = make_handler(tmp_path / "brainstorm.db")

    assert handler.static_dir.name == "static"
    assert handler.api.store.db_path == tmp_path / "brainstorm.db"
