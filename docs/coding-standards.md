# Python Coding Standards

These standards are extracted from `D:\HEBO\python_coding_standard_setup\` and
encoded in this project's `pyproject.toml`, `.pre-commit-config.yaml`, and CI.

## Runtime

- Use Python 3.10.
- Do not use syntax or standard-library features introduced in Python 3.11 or
  later.

## Formatting

- Follow PEP 8.
- Run `ruff format`.
- Keep line length at 88 characters.
- Use double quotes.
- Use four spaces for indentation.
- Keep one blank line between class methods and two between top-level
  definitions.

## Typing

- All public functions and methods must have argument and return annotations.
- Prefer Python 3.10 unions such as `str | None`.
- Prefer builtin generics such as `list[str]` and `dict[str, int]`.
- Avoid `Any`. If unavoidable, explain the reason next to the suppression.
- Run `mypy src/` in strict mode.

## Imports

- Order imports as standard library, third-party, then local application code.
- Do not use wildcard imports.
- Use `pathlib.Path` instead of `os.path`.

## Docstrings

- Use Google-style docstrings for public modules, classes, functions, and
  methods.
- Document caller-visible exceptions in a `Raises` section.
- Keep private helper docstrings optional.

## Errors

- Use project-specific exceptions from `brainstorm_tool.exceptions`.
- Do not use bare `except`.
- Do not silently swallow exceptions.
- Chain converted exceptions with `raise NewError(...) from exc`.

## Logging

- Use `logging.getLogger(__name__)` per module when logging is needed.
- Use percent-style lazy formatting in log calls.
- Do not use `print()` in library code. CLI and server startup output are allowed.

## Testing

- Tests live in `tests/` and mirror the source layout where practical.
- Use pytest.
- Cover success paths, validation paths, and persistence behavior.
- Keep coverage at or above 80%.

## Product Constraints

- Keep the runtime local-first and single-user unless a later requirement changes
  that scope.
- Keep external agent and web-search work outside the application. The
  application provides structured prompts and records returned notes.
- Store idea graph relationships explicitly in the database.
- Use GitHub for project source control only.
