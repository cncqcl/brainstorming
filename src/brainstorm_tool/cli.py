"""Command-line interface for the brainstorm workspace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from brainstorm_tool.models import IdeaStatus
from brainstorm_tool.store import BrainstormStore
from brainstorm_tool.web import serve

DEFAULT_DB = Path("data") / "brainstorm.db"


def main(argv: list[str] | None = None) -> int:
    """Run the brainstorm command-line interface.

    Args:
        argv: Optional argument list. Uses sys.argv when omitted.

    Returns:
        Process exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    store = BrainstormStore(args.db)
    result = args.handler(args, store)
    if result is not None:
        print(result)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brainstorm")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(required=True)

    init_parser = subparsers.add_parser("init", help="Create the local database")
    init_parser.set_defaults(handler=_handle_init)

    add_parser = subparsers.add_parser("add", help="Register a new idea")
    add_parser.add_argument("title")
    add_parser.add_argument("brief")
    add_parser.add_argument("--content", default=None)
    add_parser.add_argument("--content-file", type=Path, default=None)
    add_parser.add_argument("--status", choices=[status.value for status in IdeaStatus])
    add_parser.set_defaults(handler=_handle_add)

    list_parser = subparsers.add_parser("list", help="List ideas")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=_handle_list)

    show_parser = subparsers.add_parser("show", help="Show one idea as JSON")
    show_parser.add_argument("idea_id")
    show_parser.set_defaults(handler=_handle_show)

    status_parser = subparsers.add_parser("status", help="Update idea status")
    status_parser.add_argument("idea_id")
    status_parser.add_argument(
        "status",
        choices=[status.value for status in IdeaStatus],
    )
    status_parser.set_defaults(handler=_handle_status)

    version_parser = subparsers.add_parser("save-version", help="Save new version")
    version_parser.add_argument("idea_id")
    version_parser.add_argument("--content", default=None)
    version_parser.add_argument("--content-file", type=Path, default=None)
    version_parser.add_argument("--summary", default=None)
    version_parser.set_defaults(handler=_handle_save_version)

    draft_parser = subparsers.add_parser("draft", help="Cache or inspect drafts")
    draft_parser.add_argument("idea_id")
    draft_parser.add_argument("--content", default=None)
    draft_parser.add_argument("--content-file", type=Path, default=None)
    draft_parser.add_argument("--clear", action="store_true")
    draft_parser.set_defaults(handler=_handle_draft)

    comment_parser = subparsers.add_parser("comment", help="Add a comment")
    comment_parser.add_argument("idea_id")
    comment_parser.add_argument("body")
    comment_parser.add_argument("--author", default="user")
    comment_parser.add_argument("--topic", default=None)
    comment_parser.set_defaults(handler=_handle_comment)

    attachment_parser = subparsers.add_parser(
        "attach",
        help="Add attachment metadata",
    )
    attachment_parser.add_argument("idea_id")
    attachment_parser.add_argument("label")
    attachment_parser.add_argument("uri")
    attachment_parser.add_argument("--topic", default=None)
    attachment_parser.add_argument("--media-type", default=None)
    attachment_parser.set_defaults(handler=_handle_attach)

    annotate_parser = subparsers.add_parser("annotate", help="Add annotation")
    annotate_parser.add_argument("idea_id")
    annotate_parser.add_argument("body")
    annotate_parser.set_defaults(handler=_handle_annotate)

    note_parser = subparsers.add_parser("agent-note", help="Add agent research note")
    note_parser.add_argument("idea_id")
    note_parser.add_argument("topic")
    note_parser.add_argument("body")
    note_parser.add_argument("recommendation")
    note_parser.add_argument("--source-url", default=None)
    note_parser.set_defaults(handler=_handle_agent_note)

    relate_parser = subparsers.add_parser("relate", help="Connect two ideas")
    relate_parser.add_argument("source_id")
    relate_parser.add_argument("target_id")
    relate_parser.add_argument("label")
    relate_parser.set_defaults(handler=_handle_relate)

    prompt_parser = subparsers.add_parser(
        "agent-prompt",
        help="Emit a phone-agent friendly research prompt",
    )
    prompt_parser.add_argument("idea_id")
    prompt_parser.set_defaults(handler=_handle_agent_prompt)

    serve_parser = subparsers.add_parser("serve", help="Run browser dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.set_defaults(handler=_handle_serve)
    return parser


def _handle_init(args: argparse.Namespace, store: BrainstormStore) -> str:
    return f"Initialized {store.db_path}"


def _handle_add(args: argparse.Namespace, store: BrainstormStore) -> str:
    content = _read_content(args.content, args.content_file)
    status = IdeaStatus(args.status) if args.status else IdeaStatus.SEED
    idea = store.create_idea(args.title, args.brief, content, status)
    return json.dumps(idea.to_dict(), indent=2)


def _handle_list(args: argparse.Namespace, store: BrainstormStore) -> str:
    ideas = store.list_ideas()
    if args.json:
        return json.dumps([idea.to_dict() for idea in ideas], indent=2)
    if not ideas:
        return "No ideas recorded."
    lines = ["ID                                V  Status      Title"]
    for idea in ideas:
        lines.append(
            f"{idea.idea_id:<32}  {idea.version_number:<2} "
            f"{idea.status.value:<10} {idea.title}"
        )
    return "\n".join(lines)


def _handle_show(args: argparse.Namespace, store: BrainstormStore) -> str:
    return json.dumps(store.get_idea(args.idea_id).to_dict(), indent=2)


def _handle_status(args: argparse.Namespace, store: BrainstormStore) -> str:
    idea = store.update_status(args.idea_id, IdeaStatus(args.status))
    return json.dumps(idea.to_dict(), indent=2)


def _handle_save_version(args: argparse.Namespace, store: BrainstormStore) -> str:
    content = _read_content(args.content, args.content_file)
    idea = store.save_version(args.idea_id, content, args.summary)
    return json.dumps(idea.to_dict(), indent=2)


def _handle_draft(args: argparse.Namespace, store: BrainstormStore) -> str:
    if args.clear:
        store.clear_drafts(args.idea_id)
        return "Drafts cleared."
    if args.content is None and args.content_file is None:
        drafts = [draft.to_dict() for draft in store.list_drafts(args.idea_id)]
        return json.dumps(drafts, indent=2)
    draft = store.cache_draft(
        args.idea_id,
        _read_content(args.content, args.content_file),
    )
    return json.dumps(draft.to_dict() if draft else {"draft": None}, indent=2)


def _handle_comment(args: argparse.Namespace, store: BrainstormStore) -> str:
    comment = store.add_comment(args.idea_id, args.author, args.body, args.topic)
    return json.dumps(comment.to_dict(), indent=2)


def _handle_attach(args: argparse.Namespace, store: BrainstormStore) -> str:
    attachment = store.add_attachment(
        args.idea_id,
        args.label,
        args.uri,
        args.topic,
        args.media_type,
    )
    return json.dumps(attachment.to_dict(), indent=2)


def _handle_annotate(args: argparse.Namespace, store: BrainstormStore) -> str:
    annotation = store.add_annotation(args.idea_id, args.body)
    return json.dumps(annotation.to_dict(), indent=2)


def _handle_agent_note(args: argparse.Namespace, store: BrainstormStore) -> str:
    note = store.add_agent_note(
        args.idea_id,
        args.topic,
        args.body,
        args.recommendation,
        args.source_url,
    )
    return json.dumps(note.to_dict(), indent=2)


def _handle_relate(args: argparse.Namespace, store: BrainstormStore) -> str:
    relationship = store.add_relationship(args.source_id, args.target_id, args.label)
    return json.dumps(relationship.to_dict(), indent=2)


def _handle_agent_prompt(args: argparse.Namespace, store: BrainstormStore) -> str:
    idea = store.get_idea(args.idea_id)
    return (
        "Research this recorded idea and respond with concise JSON fields: "
        "topic, body, recommendation, source_url.\n\n"
        f"Title: {idea.title}\n"
        f"Status: {idea.status.value}\n"
        f"Version: {idea.current_version.version_number}\n"
        f"Brief: {idea.brief}\n\n"
        f"Content:\n{idea.current_version.content}\n\n"
        "Look for comparable projects, implementation risks, and practical "
        "recommendations. Prefer sources the user can inspect. Do not call this "
        "tool directly; paste findings back with `brainstorm agent-note` or the "
        "dashboard form."
    )


def _handle_serve(args: argparse.Namespace, store: BrainstormStore) -> None:
    serve(store.db_path, args.host, args.port)
    return None


def _read_content(content: str | None, content_file: Path | None) -> str:
    if content_file is not None:
        return content_file.read_text(encoding="utf-8")
    if content is not None:
        return content
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise ValueError("Provide --content, --content-file, or pipe content on stdin")


if __name__ == "__main__":
    raise SystemExit(main())
