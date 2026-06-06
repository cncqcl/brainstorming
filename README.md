# Brainstorm Tool

Local-first idea workspace with a browser dashboard and internal Python CLI for
agent workflows. It captures rough idea drafts, keeps accepted ideas versioned,
tracks progress status, caches editing drafts, records comments and annotations,
and stores agent research notes from phone-friendly coding agent clients.

## Product Decisions

- Single-user by design for v1; no account system or permissions layer.
- Idea content is Markdown plain text.
- Attachments are stored as metadata records, such as a local path or URL, rather
  than binary blobs in SQLite.
- Knowledge graph connections are deterministic database records. Users and
  external agents can add explicit connections.
- Coding agents do external search, reasoning, and refinement in their own
  runtime. This tool stores drafts, emits short prompts, and lets agents update
  the local database through internal commands.
- Normal users interact through natural language in the dashboard or an agent
  session. CLI commands are internal plumbing for agents, tests, and the
  dashboard backend.
- GitHub is used for project source control, not as the backing store for idea
  versions.

## Requirements

- Python 3.10
- Git for source control

## Install

```bash
python -m pip install -e ".[dev,test]"
```

## Use

Initialize the local SQLite database:

```bash
brainstorm init
```

Run the dashboard:

```bash
brainstorm open-dashboard
```

This starts the local server in a separate process and opens
`http://127.0.0.1:8765`.

Run the server in the current terminal instead:

```bash
brainstorm serve --host 127.0.0.1 --port 8765
```

Target dashboard workflow:

```text
Paste a rough idea into Quick Capture, save it, and note the draft ID.
```

Capture a rough idea through a coding agent:

```text
add a new idea: collect best practices for Claude Code, CodeX, and OpenCode
```

The agent should create a captured draft and return its draft ID.

Refine a draft through a coding agent:

```text
refine draft 12
```

The agent should load the draft, discuss details if needed, create or update the
accepted idea, mark the draft accepted, and tell you to refresh the dashboard.

Internal CLI commands used by agents:

```bash
brainstorm draft-add --source agent --message "add a new idea: ..."
brainstorm draft-list
brainstorm draft-show 12
brainstorm draft-refine-prompt 12
brainstorm draft-accept 12 <idea_id>
```

Accepted ideas can still be updated by agents:

```bash
brainstorm add "Refined title" "One-line brief" --content "Markdown body"
brainstorm save-version <idea_id> --content "Updated Markdown body"
brainstorm agent-note <idea_id> "Comparable projects" "Findings" "Recommendation"
brainstorm relate <source_id> <target_id> "feeds"
```

Proposal-first commands and packaged one-off intake skills are not part of the
normal v1 workflow. Risky future actions, such as bulk graph rewrites or draft
merges, may reintroduce proposal review later.

Attach a reference file or URL to the current idea version:

```bash
brainstorm attach <idea_id> "storage notes" "attachments/storage-notes.md" \
  --topic "risk" --media-type "text/markdown"
```

## Dashboard

- Main page: captured draft inbox, idea overview, version and status, knowledge
  graph, and quick capture entry.
- Draft inbox: each rough idea has a visible draft ID and a Refine action that
  emits a short prompt for coding agents.
- Detail page: current version editor, comments, annotations, agent notes,
  attachments, version history, draft cache.
- Editing drafts: while editing an accepted idea, the dashboard caches a draft
  every 10 minutes. The store keeps only the last five distinct drafts and
  clears them when editing is closed or a version is saved.
- Saving: saving creates a new version and leaves prior versions in history.

## Quality

The project follows the standards extracted from
`D:\HEBO\python_coding_standard_setup\`:

- Python 3.10 only.
- PEP 8 with 88-character lines and double quotes.
- Google-style docstrings on public APIs.
- Strict type checking with mypy.
- Ruff for linting, formatting, import order, pathlib use, bugbear, and security
  checks.
- Pytest coverage threshold of 80%.

Run checks:

```bash
ruff check . --fix
ruff format .
mypy src/
pytest --cov=src --cov-fail-under=80 --tb=short
```

## Repository

This directory is intended to be maintained with Git and pushed to GitHub. Create
a branch before feature work:

```bash
git checkout -b codex/<topic>
```
