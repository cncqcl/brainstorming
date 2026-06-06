"""Tests for brainstorm_tool.api."""

from __future__ import annotations

from pathlib import Path

from brainstorm_tool.api import ApiApp
from brainstorm_tool.store import BrainstormStore


def _api(tmp_path: Path) -> ApiApp:
    return ApiApp(BrainstormStore(tmp_path / "brainstorm.db"))


def test_api_creates_lists_and_fetches_idea(tmp_path: Path) -> None:
    api = _api(tmp_path)

    created = api.dispatch(
        "POST",
        "/api/ideas",
        {
            "title": "Mobile agent bridge",
            "brief": "Give agents a concise CLI contract.",
            "content": "Start with JSON-producing commands.",
            "status": "exploring",
        },
    )
    idea_id = created.body["idea_id"]
    listed = api.dispatch("GET", "/api/ideas", None)
    fetched = api.dispatch("GET", f"/api/ideas/{idea_id}", None)

    assert created.status_code == 201
    assert listed.body["ideas"][0]["title"] == "Mobile agent bridge"
    assert fetched.body["current_version"]["version_number"] == 1


def test_api_saves_draft_and_version(tmp_path: Path) -> None:
    api = _api(tmp_path)
    created = api.dispatch(
        "POST",
        "/api/ideas",
        {"title": "Drafts", "brief": "Cache edits.", "content": "Initial"},
    )
    idea_id = created.body["idea_id"]

    draft = api.dispatch(
        "POST",
        f"/api/ideas/{idea_id}/drafts",
        {"content": "Changed content"},
    )
    saved = api.dispatch(
        "POST",
        f"/api/ideas/{idea_id}/versions",
        {
            "content": "Saved content",
            "one_line_summary": "Saved a refined draft.",
        },
    )
    drafts = api.dispatch("GET", f"/api/ideas/{idea_id}/drafts", None)

    assert draft.status_code == 201
    assert saved.body["current_version"]["version_number"] == 2
    assert drafts.body["drafts"] == []


def test_api_adds_topic_comment_and_attachment(tmp_path: Path) -> None:
    api = _api(tmp_path)
    created = api.dispatch(
        "POST",
        "/api/ideas",
        {"title": "Evidence", "brief": "Keep references.", "content": "Initial"},
    )
    idea_id = created.body["idea_id"]

    comment = api.dispatch(
        "POST",
        f"/api/ideas/{idea_id}/comments",
        {"author": "user", "topic": "risk", "body": "Check storage limits."},
    )
    attachment = api.dispatch(
        "POST",
        f"/api/ideas/{idea_id}/attachments",
        {
            "topic": "risk",
            "label": "notes",
            "uri": "attachments/storage-notes.md",
            "media_type": "text/markdown",
        },
    )

    assert comment.body["topic"] == "risk"
    assert attachment.status_code == 201
    assert attachment.body["uri"] == "attachments/storage-notes.md"


def test_api_returns_not_found_for_unknown_idea(tmp_path: Path) -> None:
    api = _api(tmp_path)

    response = api.dispatch("GET", "/api/ideas/missing", None)

    assert response.status_code == 404
    assert response.body["error"] == "not_found"
