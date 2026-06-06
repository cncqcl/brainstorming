"""Tests for brainstorm_tool.cli."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from brainstorm_tool.cli import main


def _run_cli(args: list[str], capsys) -> str:
    exit_code = main(args)
    captured = capsys.readouterr()
    assert exit_code == 0
    return captured.out


def test_cli_add_list_and_show(tmp_path: Path, capsys) -> None:
    db = tmp_path / "brainstorm.db"
    output = _run_cli(
        [
            "--db",
            str(db),
            "add",
            "CLI idea",
            "Created through CLI.",
            "--content",
            "Initial content",
            "--status",
            "exploring",
        ],
        capsys,
    )
    idea_id = json.loads(output)["idea_id"]

    listed = _run_cli(["--db", str(db), "list"], capsys)
    shown = _run_cli(["--db", str(db), "show", idea_id], capsys)

    assert "CLI idea" in listed
    assert json.loads(shown)["current_version"]["content"] == "Initial content"


def test_cli_updates_supporting_records(tmp_path: Path, capsys) -> None:
    db = tmp_path / "brainstorm.db"
    idea = json.loads(
        _run_cli(
            [
                "--db",
                str(db),
                "add",
                "Record idea",
                "Add related records.",
                "--content",
                "Initial",
            ],
            capsys,
        )
    )
    idea_id = idea["idea_id"]

    _run_cli(["--db", str(db), "status", idea_id, "active"], capsys)
    _run_cli(
        ["--db", str(db), "save-version", idea_id, "--content", "Updated"],
        capsys,
    )
    _run_cli(["--db", str(db), "draft", idea_id, "--content", "Draft"], capsys)
    _run_cli(["--db", str(db), "comment", idea_id, "Looks good"], capsys)
    _run_cli(["--db", str(db), "annotate", idea_id, "Pin this"], capsys)
    _run_cli(
        [
            "--db",
            str(db),
            "agent-note",
            idea_id,
            "Comparable tools",
            "Findings",
            "Recommendation",
        ],
        capsys,
    )
    _run_cli(
        [
            "--db",
            str(db),
            "attach",
            idea_id,
            "Reference",
            "https://example.com",
        ],
        capsys,
    )

    shown = json.loads(_run_cli(["--db", str(db), "show", idea_id], capsys))
    assert shown["status"] == "active"
    assert shown["current_version"]["version_number"] == 2
    assert shown["comments"][0]["body"] == "Looks good"
    assert shown["agent_notes"][0]["recommendation"] == "Recommendation"


def test_cli_draft_workflow(tmp_path: Path, capsys) -> None:
    db = tmp_path / "brainstorm.db"
    draft = json.loads(
        _run_cli(
            [
                "--db",
                str(db),
                "draft-add",
                "--source",
                "agent",
                "--message",
                "add a new idea: collect coding agent practices",
            ],
            capsys,
        )
    )
    drafts = json.loads(_run_cli(["--db", str(db), "draft-list"], capsys))
    shown = json.loads(
        _run_cli(["--db", str(db), "draft-show", str(draft["draft_id"])], capsys)
    )
    prompt = json.loads(
        _run_cli(
            ["--db", str(db), "draft-refine-prompt", str(draft["draft_id"])],
            capsys,
        )
    )
    idea = json.loads(
        _run_cli(
            [
                "--db",
                str(db),
                "add",
                "Coding agent practices",
                "Collect reusable coding agent practices.",
                "--content",
                "Initial Markdown body.",
            ],
            capsys,
        )
    )
    accepted = json.loads(
        _run_cli(
            [
                "--db",
                str(db),
                "draft-accept",
                str(draft["draft_id"]),
                idea["idea_id"],
            ],
            capsys,
        )
    )

    assert draft["draft_id"] == 1
    assert drafts[0]["source"] == "agent"
    assert shown["raw_message"] == "add a new idea: collect coding agent practices"
    assert "Refine draft 1" in prompt["prompt"]
    assert prompt["draft"]["status"] == "refining"
    assert accepted["status"] == "accepted"
    assert accepted["accepted_idea_id"] == idea["idea_id"]


def test_cli_agent_prompt_and_relationship(tmp_path: Path, capsys) -> None:
    db = tmp_path / "brainstorm.db"
    first = json.loads(
        _run_cli(
            ["--db", str(db), "add", "First", "First brief.", "--content", "One"],
            capsys,
        )
    )
    second = json.loads(
        _run_cli(
            ["--db", str(db), "add", "Second", "Second brief.", "--content", "Two"],
            capsys,
        )
    )

    relationship = json.loads(
        _run_cli(
            [
                "--db",
                str(db),
                "relate",
                first["idea_id"],
                second["idea_id"],
                "feeds",
            ],
            capsys,
        )
    )
    prompt = _run_cli(["--db", str(db), "agent-prompt", first["idea_id"]], capsys)

    assert relationship["label"] == "feeds"
    assert "Research this recorded idea" in prompt


def test_cli_open_dashboard_starts_server_process(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    db = tmp_path / "brainstorm.db"
    calls: list[dict[str, Any]] = []

    class FakeProcess:
        pid = 12345

    def fake_popen(command: list[str], **kwargs: Any) -> FakeProcess:
        calls.append({"command": command, "kwargs": kwargs})
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr("brainstorm_tool.cli.time.sleep", lambda _seconds: None)
    monkeypatch.setattr("brainstorm_tool.cli.webbrowser.open", lambda _url: True)

    output = _run_cli(
        [
            "--db",
            str(db),
            "open-dashboard",
            "--host",
            "127.0.0.1",
            "--port",
            "8766",
        ],
        capsys,
    )

    assert "http://127.0.0.1:8766/" in output
    assert calls[0]["command"] == [
        sys.executable,
        "-m",
        "brainstorm_tool.cli",
        "--db",
        str(db),
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "8766",
    ]
