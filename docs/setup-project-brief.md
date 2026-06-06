# Brainstorm Tool Project Brief

## Snapshot

Brainstorm Tool is a local-first, single-user idea workspace. It combines a
Python CLI, SQLite persistence, and a browser dashboard for capturing ideas,
versioning Markdown content, caching editing drafts, recording comments and
annotations, attaching reference metadata, storing external agent research
notes, and maintaining explicit knowledge graph relationships.

The project is intentionally not a multi-user collaboration system in v1. It
does not use GitHub as an idea backing store, and it expects external coding
agents to do their own search or reasoning outside the application.

## Current Implementation

| Area | Status | Evidence |
| --- | --- | --- |
| Packaging | Present | `pyproject.toml` defines `brainstorm-tool`, Python `>=3.10`, editable install extras, and the `brainstorm` console script. |
| CLI | Present | `src/brainstorm_tool/cli.py` defines commands for init, add, list, show, status, save-version, draft, comment, attach, agent prompts, notes, relationships, and serving the dashboard. |
| API | Present | `src/brainstorm_tool/api.py` dispatches JSON routes for ideas, graph, status, versions, drafts, comments, attachments, annotations, agent notes, and relationships. |
| Persistence | Present | `src/brainstorm_tool/store.py` creates SQLite tables for ideas, versions, drafts, comments, annotations, attachments, agent notes, and relationships. |
| Web dashboard | Present | `src/brainstorm_tool/web.py` serves static assets and forwards `/api/` traffic to the API dispatcher. Static UI assets live under `src/brainstorm_tool/static/`. |
| Domain model | Present | `src/brainstorm_tool/models.py` defines idea statuses, versions, summaries, details, comments, annotations, attachments, agent notes, relationships, and graph DTOs. |
| Tests | Present | `tests/test_store.py`, `tests/test_api.py`, and `tests/test_web.py` cover core persistence, API, and handler setup behavior. |
| Standards | Present | `docs/coding-standards.md` and `pyproject.toml` encode Ruff, mypy strict mode, pytest, and coverage expectations. |
| Runtime data | Present | `data/brainstorm.db` exists in the workspace. |

## Product Decisions

| Decision | Current Direction |
| --- | --- |
| User model | Single-user for v1; no accounts or permission layer. |
| Content format | Idea content is Markdown plain text. |
| Attachments | Store metadata records such as local paths or URLs, not binary blobs. |
| Knowledge graph | Use deterministic database records for explicit user or agent-created links. |
| Agent workflow | Emit prompts and record submitted notes; external agents perform research in their own runtime. |
| Source control | Use GitHub for project source control only. |

## Covered Behavior

Tests currently confirm that ideas start at version one, version saves increment
history and clear drafts, draft caching keeps the last five distinct changes,
comments and annotations attach to the current version, attachments link to the
current version, relationships populate the knowledge graph, API routes create
and fetch ideas, API draft/version behavior works, comments and attachments can
be added through the API, missing ideas return `404`, and the dashboard handler
binds API and static asset paths.

## Risks And Gaps

| Risk or Gap | Why It Matters | Suggested Next Step |
| --- | --- | --- |
| Dashboard behavior is only lightly tested | Static UI workflows are core to the product experience but currently have minimal automated coverage. | Add browser-level or API-backed UI tests for creating, editing, saving, and closing an idea. |
| Validation surface may be uneven | The API validates typed text fields and statuses, but broader edge cases are not visible from the current tests. | Add tests for malformed payloads, duplicate or invalid relationships, missing fields, and invalid draft/version flows. |
| Runtime data is untracked context | `data/brainstorm.db` exists locally, but its intended lifecycle is not documented in the brief or standards. | Decide whether local databases should be ignored, seeded, migrated, or treated as developer-only state. |
| Quality gate is only partially verified | The local pytest suite passes, but Ruff, mypy, and coverage were not run in this setup pass. | Run the full quality gate locally and record failures or environment gaps. |
| Product roadmap is implicit | The current README explains v1 decisions, but no explicit next milestone is captured. | Create a short roadmap with dashboard coverage, data lifecycle, import/export, and agent workflow improvements. |

## Verification

`D:\conda_envs\Py310\python.exe -m pytest --tb=short --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex`
passed 11 tests on Python 3.10.20. Ruff, mypy, and coverage should still be run
before treating this as release-ready validation.

## Recommended Next Actions

1. Run `pytest --cov=src --cov-fail-under=80 --tb=short` under Python 3.10 to
   confirm the target-runtime coverage baseline.
2. Run `ruff check .`, `ruff format --check .`, and `mypy src/` to verify the
   standards encoded in `pyproject.toml`.
3. Decide the lifecycle for `data/brainstorm.db` and any local dashboard log
   files before committing more work.
4. Add validation tests for API error paths and relationship constraints.
5. Add one dashboard workflow test that exercises create, edit, draft, save, and
   detail rendering through the browser interface.
6. Add a short `docs/roadmap.md` that names the next product milestone and
   separates v1 scope from later collaboration or export features.

## Open Questions

| Question | Default Until Decided |
| --- | --- |
| Should local database files be committed, ignored, or replaced by explicit fixtures? | Treat them as developer-local runtime state. |
| Should the dashboard be tested through a browser runner or lower-level API and DOM tests? | Start with one browser workflow because the product has a real dashboard surface. |
| What is the next user-facing milestone after the scaffold? | Improve confidence in the edit/save/dashboard loop before adding new product breadth. |
