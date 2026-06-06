# Codex Project Instructions

## Python Environment

Use the conda `Py310` environment for this project.

- Preferred interpreter: `D:\conda_envs\Py310\python.exe`
- Do not use bare `python` for project verification; it may resolve to the
  system Anaconda Python instead of the project target runtime.
- Prefer direct interpreter commands over shell activation, because Codex tool
  calls may not preserve activated conda state between commands.

## Common Commands

Install or refresh the editable project dependencies:

```powershell
D:\conda_envs\Py310\python.exe -m pip install -e ".[dev,test]"
```

Run tests with a workspace-local temp directory:

```powershell
D:\conda_envs\Py310\python.exe -m pytest --tb=short --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex
```

Run the full quality gate:

```powershell
D:\conda_envs\Py310\python.exe -m ruff check .
D:\conda_envs\Py310\python.exe -m ruff format --check .
D:\conda_envs\Py310\python.exe -m mypy src/
D:\conda_envs\Py310\python.exe -m pytest --cov=src --cov-fail-under=80 --tb=short --basetemp C:\Users\cncqc\Documents\brainstorming\.pytest-tmp-codex
```

Open the dashboard in a separate server process and browser:

```powershell
D:\conda_envs\Py310\python.exe -m brainstorm_tool.cli open-dashboard --host 127.0.0.1 --port 8765
```

Run the dashboard server in the current terminal for debugging:

```powershell
D:\conda_envs\Py310\python.exe -m brainstorm_tool.cli serve --host 127.0.0.1 --port 8765
```

## Brainstorm Tool Agent Workflow

Follow `docs/agent-workflow.md` when users interact with this project through a
coding agent.

- Users speak naturally. Do not ask users to run CLI commands unless debugging
  the tool itself.
- If the user says "add a new idea: ..." or "record this idea: ...", capture it
  as an idea draft and return the draft ID.
- If the user says "refine draft N", load that draft, discuss details with the
  user if needed, create or update the accepted idea, mark the draft accepted,
  and tell the user to refresh the dashboard.
- CLI/API commands are internal plumbing for agents, tests, and the dashboard
  backend.
- Keep the v1 workflow simple. Do not reintroduce proposal-first refinement or
  packaged one-off intake skills unless the user explicitly asks for a safety
  review workflow.

## Notes For Future Codex Sessions

- Keep implementation compatible with Python 3.10.
- Use the existing Ruff, mypy, pytest, and coverage settings from
  `pyproject.toml`.
- If pytest fails with a permission error under `AppData\Local\Temp`, rerun it
  with the workspace-local `--basetemp` shown above.
