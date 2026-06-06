# Brainstorm Tool

Local-first idea workspace with a Python CLI and a browser dashboard. It keeps
ideas versioned, tracks progress status, caches editing drafts, records comments
and annotations, and stores agent research notes from phone-friendly coding
agent clients.

## Product Decisions

- Single-user by design for v1; no account system or permissions layer.
- Idea content is Markdown plain text.
- Attachments are stored as metadata records, such as a local path or URL, rather
  than binary blobs in SQLite.
- Knowledge graph connections are deterministic database records. Users and
  external agents can add explicit connections.
- Coding agents do external search or reasoning in their own runtime. This tool
  only emits prompts and accepts pasted/submitted results.
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

Register an idea:

```bash
brainstorm add "Pocket agent bridge" "CLI contract for mobile agents" \
  --content "Support JSON outputs and agent research notes." \
  --status exploring
```

Run the dashboard:

```bash
brainstorm serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`.

Emit a concise prompt for a phone-based coding agent:

```bash
brainstorm agent-prompt <idea_id>
```

After the agent researches comparable tools, risks, and recommendations, record
the result:

```bash
brainstorm agent-note <idea_id> "Comparable projects" \
  "Found several local-first knowledge managers." \
  "Keep the storage portable and the API JSON-first." \
  --source-url "https://example.com"
```

Attach a reference file or URL to the current version:

```bash
brainstorm attach <idea_id> "storage notes" "attachments/storage-notes.md" \
  --topic "risk" --media-type "text/markdown"
```

## Dashboard

- Main page: idea overview, version and status, knowledge graph, new idea entry.
- Detail page: current version editor, comments, annotations, agent notes,
  attachments, version history, draft cache.
- Drafts: while editing, the dashboard caches a draft every 10 minutes. The
  store keeps only the last five distinct drafts and clears them when editing is
  closed or a version is saved.
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
