# Simple Draft Agent Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a simple draft-first workflow where users capture rough ideas in
the dashboard or through an agent, then ask an agent to refine a draft by ID and
update the local database.

**Architecture:** Add a separate captured-draft model/table for rough incoming
messages, distinct from existing edit autosave drafts. The dashboard and agent
skill both use the same draft capture operations. Remove the old bundled
`new_idea` skill and proposal-first CLI commands so there is only one normal
workflow.

**Tech Stack:** Python 3.10, SQLite, stdlib HTTP server, vanilla HTML/CSS/JS,
Ruff, mypy, pytest.

## Scope

Implement the v1 workflow:

- Capture a raw idea draft from dashboard or agent.
- Assign and show a stable draft ID.
- Generate a short prompt for refining a draft by ID.
- Let the agent create/update ideas directly after user discussion.
- Mark a captured draft as accepted and link it to the resulting idea.
- Keep graph relationship creation explicit and deterministic.

Do not build an in-app LLM runner. Do not keep proposal review in the normal
draft-refinement path.

## Task 1: Add Captured Draft Model

**Files:**

- Modify: `src/brainstorm_tool/models.py`
- Test: `tests/test_store.py`

**Step 1: Write the failing test**

Add a store test that expects a captured draft object:

```python
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
```

**Step 2: Run test to verify it fails**

Run:

```powershell
D:\conda_envs\Py310\python.exe -m pytest tests/test_store.py::test_capture_idea_draft_returns_visible_id -q --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex
```

Expected: failure because `capture_idea_draft` and the model do not exist.

**Step 3: Add model**

Add `IdeaDraftStatus` and `IdeaDraft` to `models.py`:

```python
class IdeaDraftStatus(str, Enum):
    """Lifecycle status for a captured rough idea draft."""

    CAPTURED = "captured"
    REFINING = "refining"
    ACCEPTED = "accepted"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class IdeaDraft:
    """Raw idea message captured before refinement."""

    draft_id: int
    raw_message: str
    source: str
    status: IdeaDraftStatus
    created_at: str
    updated_at: str
    refinement_prompt: str
    last_refined_at: str | None
    accepted_idea_id: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "draft_id": self.draft_id,
            "raw_message": self.raw_message,
            "source": self.source,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "refinement_prompt": self.refinement_prompt,
            "last_refined_at": self.last_refined_at,
            "accepted_idea_id": self.accepted_idea_id,
        }
```

**Step 4: Run test again**

Expected: still fails because persistence is not implemented.

## Task 2: Add Captured Draft Persistence

**Files:**

- Modify: `src/brainstorm_tool/store.py`
- Test: `tests/test_store.py`

**Step 1: Add failing tests**

Add tests for list/show, prompt generation, and accepted linking:

```python
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
    assert updated.status.value == "refining"


def test_accept_idea_draft_links_to_idea(tmp_path: Path) -> None:
    store = _store(tmp_path)
    draft = store.capture_idea_draft("rough idea", source="agent")
    idea = store.create_idea("Refined", "Refined brief.", "Refined body.")

    accepted = store.accept_idea_draft(draft.draft_id, idea.idea_id)

    assert accepted.status.value == "accepted"
    assert accepted.accepted_idea_id == idea.idea_id
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
D:\conda_envs\Py310\python.exe -m pytest tests/test_store.py -q --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex
```

Expected: new tests fail.

**Step 3: Create schema**

Add `idea_drafts` table in `_create_schema`:

```sql
CREATE TABLE IF NOT EXISTS idea_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_message TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    refinement_prompt TEXT NOT NULL,
    last_refined_at TEXT,
    accepted_idea_id TEXT,
    FOREIGN KEY (accepted_idea_id)
        REFERENCES ideas(id)
        ON DELETE SET NULL
);
```

**Step 4: Implement store methods**

Add public methods:

- `capture_idea_draft(raw_message: str, source: str) -> IdeaDraft`
- `list_idea_drafts() -> list[IdeaDraft]`
- `get_idea_draft(draft_id: int) -> IdeaDraft`
- `refinement_prompt(draft_id: int) -> str`
- `accept_idea_draft(draft_id: int, idea_id: str) -> IdeaDraft`
- `archive_idea_draft(draft_id: int) -> IdeaDraft`

Use this prompt template:

```text
Refine draft {draft_id} using the Brainstorm Tool project skill. Ask me any
needed questions, update the local database when the refined idea is ready, mark
the draft accepted, and tell me to refresh the dashboard.
```

**Step 5: Run store tests**

Expected: all `tests/test_store.py` tests pass.

## Task 3: Add Draft API Routes

**Files:**

- Modify: `src/brainstorm_tool/api.py`
- Test: `tests/test_api.py`

**Step 1: Write failing API tests**

Add:

```python
def test_api_captures_and_lists_idea_drafts(tmp_path: Path) -> None:
    api = _api(tmp_path)

    created = api.dispatch(
        "POST",
        "/api/drafts",
        {"raw_message": "add a new idea: dashboard inbox", "source": "dashboard"},
    )
    listed = api.dispatch("GET", "/api/drafts", None)

    assert created.status_code == 201
    assert created.body["draft_id"] == 1
    assert listed.body["drafts"][0]["raw_message"] == (
        "add a new idea: dashboard inbox"
    )


def test_api_returns_refinement_prompt(tmp_path: Path) -> None:
    api = _api(tmp_path)
    created = api.dispatch(
        "POST",
        "/api/drafts",
        {"raw_message": "rough idea", "source": "dashboard"},
    )

    prompt = api.dispatch("POST", "/api/drafts/1/refine-prompt", None)

    assert prompt.status_code == 200
    assert "Refine draft 1" in prompt.body["prompt"]
    assert prompt.body["draft"]["status"] == "refining"
```

**Step 2: Run test to verify failure**

Run:

```powershell
D:\conda_envs\Py310\python.exe -m pytest tests/test_api.py -q --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex
```

**Step 3: Implement routes**

Add routes:

- `GET /api/drafts`
- `POST /api/drafts`
- `GET /api/drafts/{draft_id}`
- `POST /api/drafts/{draft_id}/refine-prompt`
- `POST /api/drafts/{draft_id}/accept`
- `POST /api/drafts/{draft_id}/archive`

**Step 4: Run API tests**

Expected: API tests pass.

## Task 4: Add Agent/Internal CLI Commands

**Files:**

- Modify: `src/brainstorm_tool/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write failing CLI tests**

Add tests for:

- `draft-add --source agent --message "add a new idea: ..."`
- `draft-list`
- `draft-show 1`
- `draft-refine-prompt 1`
- `draft-accept 1 <idea_id>`

Use JSON output for commands that agents consume.

**Step 2: Run test to verify failure**

Run:

```powershell
D:\conda_envs\Py310\python.exe -m pytest tests/test_cli.py -q --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex
```

**Step 3: Implement commands**

Add:

- `draft-add`
- `draft-list`
- `draft-show`
- `draft-refine-prompt`
- `draft-accept`
- `draft-archive`

Use hidden/internal help wording:

```text
Internal agent command: capture a raw idea draft.
```

Keep existing idea commands for agent use:

- `add`
- `save-version`
- `agent-note`
- `relate`

**Step 4: Run CLI tests**

Expected: CLI tests pass.

## Task 5: Remove Unused Skill And Proposal Commands

**Files:**

- Modify: `src/brainstorm_tool/cli.py`
- Modify: `src/brainstorm_tool/models.py`
- Modify: `src/brainstorm_tool/store.py`
- Modify: `pyproject.toml`
- Delete: `src/brainstorm_tool/skills.py`
- Delete: `src/brainstorm_tool/skills/new_idea/SKILL.md`
- Delete: `src/brainstorm_tool/skills/new_idea/schema.json`
- Test: `tests/test_cli.py`
- Test: `tests/test_store.py`
- Delete or rewrite: `tests/test_skills.py`

**Step 1: Write cleanup expectation**

Update tests so these commands are no longer expected:

- `skill-list`
- `skill-show`
- `proposal-create`
- `proposal-list`
- `proposal-show`
- `proposal-apply`

**Step 2: Remove CLI imports and handlers**

Remove:

- `from brainstorm_tool.skills import get_skill, list_skills`
- `_handle_skill_list`
- `_handle_skill_show`
- `_handle_proposal_create`
- `_handle_proposal_list`
- `_handle_proposal_show`
- `_handle_proposal_apply`
- `_read_json_object`, if no longer used

**Step 3: Remove proposal and skill model code**

Remove:

- `SkillDefinition`
- `Proposal`
- `create_proposal`
- `list_proposals`
- `get_proposal`
- `apply_proposal`
- proposal helper methods
- `proposals` table creation

Existing local databases may still contain the old `proposals` table. That is
acceptable; the application ignores it.

**Step 4: Remove package data**

Remove this from `pyproject.toml` if no packaged skills remain:

```toml
[tool.setuptools.package-data]
brainstorm_tool = ["static/*", "skills/*/*"]
```

Replace with:

```toml
[tool.setuptools.package-data]
brainstorm_tool = ["static/*"]
```

**Step 5: Run targeted tests**

Run:

```powershell
D:\conda_envs\Py310\python.exe -m pytest tests/test_store.py tests/test_cli.py -q --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex
```

Expected: pass.

## Task 6: Add Project Agent Skill Documentation

**Files:**

- Create: `.codex/skills/brainstorming-project-agent/SKILL.md` or `docs/agent-workflow.md`
- Modify: `AGENTS.md`
- Modify: `README.md`

**Step 1: Decide location**

Prefer repo documentation first:

- `docs/agent-workflow.md` is committed and visible to all agents.
- `AGENTS.md` tells Codex to follow that document.

Only create a repo-local `.codex/skills/...` later if Codex supports loading
project-local skills reliably in this setup.

**Step 2: Write agent workflow document**

Create `docs/agent-workflow.md` with these rules:

```markdown
# Agent Workflow

Users speak naturally. Do not ask users to run CLI commands.

If the user says "add a new idea: ..." or "record this idea: ...":
1. Capture the message as a draft with source `agent`.
2. Return the draft ID.
3. Ask whether they want to refine now or later.

If the user says "refine draft N":
1. Load draft N.
2. Read existing idea summaries and graph context.
3. Ask at most one clarifying question at a time when needed.
4. Create or update the accepted idea directly.
5. Add research notes or relationships only when they are concrete.
6. Mark the draft accepted and link it to the idea.
7. Tell the user to refresh the dashboard.
```

**Step 3: Update AGENTS**

Add a "Brainstorm Tool Agent Workflow" section pointing to
`docs/agent-workflow.md`.

**Step 4: Update README**

Replace proposal-first examples with natural language examples:

```text
Dashboard: type a rough idea and click Save Draft.
Agent: "add a new idea: ..."
Agent: "refine draft 12"
```

## Task 7: Dashboard Inbox And Refine Button

**Files:**

- Modify: `src/brainstorm_tool/static/index.html`
- Modify: `src/brainstorm_tool/static/app.js`
- Modify: `src/brainstorm_tool/static/app.css`
- Test: `tests/test_web.py`

**Step 1: Add API-backed UI**

Add:

- Quick capture textarea.
- Save Draft button.
- Inbox list showing draft ID, source, status, and message preview.
- Refine button per draft.
- Prompt display/copy area.

**Step 2: Keep behavior simple**

The button calls `POST /api/drafts/{id}/refine-prompt`, then displays the
prompt. It does not call an LLM service.

**Step 3: Add web/API smoke test**

Extend existing web tests to confirm `/api/drafts` works through the HTTP
handler.

## Task 8: Full Verification

**Files:**

- No source edits unless failures require fixes.

**Step 1: Run Ruff**

```powershell
D:\conda_envs\Py310\python.exe -m ruff check .
```

Expected: no lint errors.

**Step 2: Run format check**

```powershell
D:\conda_envs\Py310\python.exe -m ruff format --check .
```

Expected: no formatting changes needed.

**Step 3: Run mypy**

```powershell
D:\conda_envs\Py310\python.exe -m mypy src/
```

Expected: no type errors.

**Step 4: Run coverage gate**

```powershell
D:\conda_envs\Py310\python.exe -m pytest --cov=src --cov-fail-under=80 --tb=short --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex
```

Expected: all tests pass and coverage is at least 80%.

## Commit Strategy

Make small commits after green tests:

1. `feat: add captured idea drafts`
2. `feat: expose draft workflow to api and cli`
3. `chore: remove proposal-first workflow`
4. `docs: document simple draft agent workflow`
5. `feat: add dashboard draft inbox`

Do not commit runtime data under `data/`.
