"""JSON API dispatcher used by the web server and tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from brainstorm_tool.exceptions import AppError, NotFoundError, ValidationError
from brainstorm_tool.models import IdeaStatus
from brainstorm_tool.store import BrainstormStore

JsonBody: TypeAlias = dict[str, object]
Payload: TypeAlias = Mapping[str, object] | None


@dataclass(frozen=True)
class ApiResponse:
    """HTTP-like response returned by the API dispatcher."""

    status_code: int
    body: JsonBody


class ApiApp:
    """Route JSON requests to brainstorm store operations."""

    def __init__(self, store: BrainstormStore) -> None:
        """Initialize the app with a persistence store.

        Args:
            store: Store used to serve API requests.
        """
        self.store = store

    def dispatch(self, method: str, path: str, payload: Payload) -> ApiResponse:
        """Dispatch a JSON request.

        Args:
            method: HTTP verb such as GET or POST.
            path: Request path beginning with /api.
            payload: Parsed JSON request body for mutating operations.

        Returns:
            API response with status code and JSON-compatible body.
        """
        try:
            return self._dispatch(method.upper(), path.strip("/").split("/"), payload)
        except NotFoundError as exc:
            return ApiResponse(404, {"error": "not_found", "message": str(exc)})
        except ValidationError as exc:
            return ApiResponse(400, {"error": "validation_error", "message": str(exc)})
        except AppError as exc:
            return ApiResponse(500, {"error": "app_error", "message": str(exc)})

    def _dispatch(
        self,
        method: str,
        segments: list[str],
        payload: Payload,
    ) -> ApiResponse:
        if segments == ["api", "ideas"] and method == "GET":
            ideas = [idea.to_dict() for idea in self.store.list_ideas()]
            return ApiResponse(200, {"ideas": ideas})

        if segments == ["api", "ideas"] and method == "POST":
            body = _payload(payload)
            idea = self.store.create_idea(
                title=_text(body, "title"),
                brief=_text(body, "brief"),
                content=_text(body, "content"),
                status=_status(body.get("status", IdeaStatus.SEED.value)),
            )
            return ApiResponse(201, idea.to_dict())

        if segments == ["api", "graph"] and method == "GET":
            return ApiResponse(200, self.store.get_knowledge_graph().to_dict())

        if len(segments) >= 3 and segments[:2] == ["api", "ideas"]:
            idea_id = segments[2]
            if len(segments) == 3 and method == "GET":
                return ApiResponse(200, self.store.get_idea(idea_id).to_dict())
            if len(segments) == 4:
                return self._dispatch_idea_child(method, idea_id, segments[3], payload)

        return ApiResponse(404, {"error": "not_found", "message": "Unknown route"})

    def _dispatch_idea_child(
        self,
        method: str,
        idea_id: str,
        child: str,
        payload: Payload,
    ) -> ApiResponse:
        if child == "status" and method == "POST":
            body = _payload(payload)
            idea = self.store.update_status(idea_id, _status(body.get("status")))
            return ApiResponse(200, idea.to_dict())

        if child == "versions" and method == "POST":
            body = _payload(payload)
            idea = self.store.save_version(
                idea_id,
                _text(body, "content"),
                _optional_text(body, "one_line_summary"),
            )
            return ApiResponse(200, idea.to_dict())

        if child == "drafts" and method == "GET":
            drafts = [draft.to_dict() for draft in self.store.list_drafts(idea_id)]
            return ApiResponse(200, {"drafts": drafts})

        if child == "drafts" and method == "POST":
            body = _payload(payload)
            draft = self.store.cache_draft(idea_id, _text(body, "content"))
            status_code = 201 if draft is not None else 200
            return ApiResponse(
                status_code,
                {"draft": draft.to_dict() if draft is not None else None},
            )

        if child == "drafts" and method == "DELETE":
            self.store.clear_drafts(idea_id)
            return ApiResponse(204, {})

        if child == "close-editing" and method == "POST":
            return ApiResponse(200, self.store.close_editing(idea_id).to_dict())

        if child == "comments" and method == "POST":
            body = _payload(payload)
            comment = self.store.add_comment(
                idea_id,
                _text(body, "author", default="user"),
                _text(body, "body"),
                _optional_text(body, "topic"),
            )
            return ApiResponse(201, comment.to_dict())

        if child == "attachments" and method == "POST":
            body = _payload(payload)
            attachment = self.store.add_attachment(
                idea_id,
                label=_text(body, "label"),
                uri=_text(body, "uri"),
                topic=_optional_text(body, "topic"),
                media_type=_optional_text(body, "media_type"),
            )
            return ApiResponse(201, attachment.to_dict())

        if child == "annotations" and method == "POST":
            body = _payload(payload)
            annotation = self.store.add_annotation(idea_id, _text(body, "body"))
            return ApiResponse(201, annotation.to_dict())

        if child == "agent-notes" and method == "POST":
            body = _payload(payload)
            note = self.store.add_agent_note(
                idea_id,
                topic=_text(body, "topic"),
                body=_text(body, "body"),
                recommendation=_text(body, "recommendation"),
                source_url=_optional_text(body, "source_url"),
            )
            return ApiResponse(201, note.to_dict())

        if child == "relationships" and method == "POST":
            body = _payload(payload)
            relationship = self.store.add_relationship(
                idea_id,
                _text(body, "target_id"),
                _text(body, "label"),
            )
            return ApiResponse(201, relationship.to_dict())

        return ApiResponse(404, {"error": "not_found", "message": "Unknown route"})


def _payload(payload: Payload) -> Mapping[str, object]:
    if payload is None:
        return {}
    return payload


def _text(body: Mapping[str, object], key: str, default: str | None = None) -> str:
    value = body.get(key, default)
    if not isinstance(value, str):
        raise ValidationError(f"{key} must be a string")
    if not value.strip():
        raise ValidationError(f"{key} must not be empty")
    return value


def _optional_text(body: Mapping[str, object], key: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{key} must be a string")
    return value if value.strip() else None


def _status(value: object) -> IdeaStatus:
    if not isinstance(value, str):
        raise ValidationError("status must be a string")
    try:
        return IdeaStatus(value)
    except ValueError as exc:
        allowed = ", ".join(status.value for status in IdeaStatus)
        raise ValidationError(f"status must be one of: {allowed}") from exc
