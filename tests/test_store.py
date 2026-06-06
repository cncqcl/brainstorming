"""Tests for brainstorm_tool.store."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from brainstorm_tool.models import IdeaStatus
from brainstorm_tool.store import BrainstormStore


def _store(tmp_path: Path) -> BrainstormStore:
    return BrainstormStore(tmp_path / "brainstorm.db")


def test_create_idea_starts_at_version_one(tmp_path: Path) -> None:
    store = _store(tmp_path)

    idea = store.create_idea(
        title="Pocket agent inbox",
        brief="Collect agent-ready tasks from mobile clients.",
        content="Build a compact inbox for prompts and responses.",
        status=IdeaStatus.EXPLORING,
    )

    assert idea.current_version.version_number == 1
    assert idea.status == IdeaStatus.EXPLORING
    assert idea.current_version.content == (
        "Build a compact inbox for prompts and responses."
    )


def test_capture_idea_draft_returns_visible_id(tmp_path: Path) -> None:
    store = _store(tmp_path)

    draft = store.capture_idea_draft(
        raw_message="add a new idea: collect agent best practices",
        source="agent",
    )

    assert draft.draft_id == 1
    assert draft.raw_message == "add a new idea: collect agent best practices"
    assert draft.source == "agent"
    assert draft.status == "captured"
    assert draft.accepted_idea_id is None


def test_list_and_get_idea_drafts(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.capture_idea_draft("first idea", source="dashboard")
    second = store.capture_idea_draft("second idea", source="agent")

    drafts = store.list_idea_drafts()

    assert [draft.draft_id for draft in drafts] == [
        second.draft_id,
        first.draft_id,
    ]
    assert store.get_idea_draft(first.draft_id).raw_message == "first idea"


def test_refine_prompt_marks_draft_refining(tmp_path: Path) -> None:
    store = _store(tmp_path)
    draft = store.capture_idea_draft("rough idea", source="dashboard")

    prompt = store.refinement_prompt(draft.draft_id)
    updated = store.get_idea_draft(draft.draft_id)

    assert "Refine draft 1" in prompt
    assert "Brainstorm Tool project skill" in prompt
    assert updated.status == "refining"


def test_accept_idea_draft_links_to_idea(tmp_path: Path) -> None:
    store = _store(tmp_path)
    draft = store.capture_idea_draft("rough idea", source="agent")
    idea = store.create_idea("Refined", "Refined brief.", "Refined body.")

    accepted = store.accept_idea_draft(draft.draft_id, idea.idea_id)

    assert accepted.status == "accepted"
    assert accepted.accepted_idea_id == idea.idea_id


def test_cache_draft_keeps_last_five_real_differences(tmp_path: Path) -> None:
    store = _store(tmp_path)
    idea = store.create_idea("Graph", "Map idea links.", "Current version")

    assert store.cache_draft(idea.idea_id, "Current version") is None

    for index in range(7):
        cached = store.cache_draft(
            idea.idea_id,
            f"Draft {index}",
            now=datetime(2026, 1, index + 1, tzinfo=timezone.utc),
        )
        assert cached is not None

    duplicate = store.cache_draft(idea.idea_id, "Draft 6")

    drafts = store.list_drafts(idea.idea_id)
    assert duplicate is None
    assert [draft.content for draft in drafts] == [
        "Draft 2",
        "Draft 3",
        "Draft 4",
        "Draft 5",
        "Draft 6",
    ]


def test_save_version_increments_history_and_clears_drafts(tmp_path: Path) -> None:
    store = _store(tmp_path)
    idea = store.create_idea("CLI", "Phone friendly CLI.", "First content")
    store.cache_draft(idea.idea_id, "Unsaved content")

    updated = store.save_version(
        idea.idea_id,
        "Second content",
        one_line_summary="Refined the CLI workflow.",
    )

    history = store.list_history(idea.idea_id)
    assert updated.current_version.version_number == 2
    assert [version.one_line_summary for version in history] == [
        "Phone friendly CLI.",
        "Refined the CLI workflow.",
    ]
    assert store.list_drafts(idea.idea_id) == []


def test_notes_and_annotations_attach_to_current_version(tmp_path: Path) -> None:
    store = _store(tmp_path)
    idea = store.create_idea("Research loop", "Agent research notes.", "Initial")
    store.save_version(idea.idea_id, "Updated")

    store.add_comment(
        idea.idea_id,
        "alice",
        "Needs a status taxonomy.",
        topic="workflow",
    )
    store.add_annotation(idea.idea_id, "Pin this for the next sprint.")
    store.add_agent_note(
        idea.idea_id,
        topic="Existing tools",
        body="Compare with personal knowledge managers.",
        recommendation="Keep storage local-first and exportable.",
        source_url="https://example.com/research",
    )

    detail = store.get_idea(idea.idea_id)
    assert detail.current_version.version_number == 2
    assert detail.comments[0].topic == "workflow"
    assert detail.comments[0].body == "Needs a status taxonomy."
    assert detail.annotations[0].body == "Pin this for the next sprint."
    assert detail.agent_notes[0].recommendation == (
        "Keep storage local-first and exportable."
    )


def test_attachments_link_to_current_version(tmp_path: Path) -> None:
    store = _store(tmp_path)
    idea = store.create_idea("Attachments", "Attach local references.", "Initial")
    store.save_version(idea.idea_id, "Updated")

    attachment = store.add_attachment(
        idea.idea_id,
        label="architecture sketch",
        uri="attachments/sketch.md",
        topic="dashboard",
        media_type="text/markdown",
    )

    detail = store.get_idea(idea.idea_id)
    assert attachment.version_number == 2
    assert detail.attachments[0].topic == "dashboard"
    assert detail.attachments[0].uri == "attachments/sketch.md"


def test_knowledge_graph_uses_registered_relationships(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.create_idea("Inbox", "Capture new ideas.", "Content")
    second = store.create_idea("Review", "Iterate captured ideas.", "Content")

    store.add_relationship(first.idea_id, second.idea_id, "feeds")

    graph = store.get_knowledge_graph()
    assert [node.title for node in graph.nodes] == ["Inbox", "Review"]
    assert graph.edges[0].label == "feeds"
