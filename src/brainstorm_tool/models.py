"""Domain models for ideas, versions, notes, and graph data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IdeaStatus(str, Enum):
    """Progress status for an idea."""

    SEED = "seed"
    EXPLORING = "exploring"
    ACTIVE = "active"
    PAUSED = "paused"
    RESEARCHED = "researched"
    SHIPPED = "shipped"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class IdeaVersion:
    """Stored version of an idea body."""

    idea_id: str
    version_number: int
    content: str
    one_line_summary: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "idea_id": self.idea_id,
            "version_number": self.version_number,
            "content": self.content,
            "one_line_summary": self.one_line_summary,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class IdeaSummary:
    """Compact idea row used by overview screens."""

    idea_id: str
    title: str
    brief: str
    status: IdeaStatus
    version_number: int
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "idea_id": self.idea_id,
            "title": self.title,
            "brief": self.brief,
            "status": self.status.value,
            "version_number": self.version_number,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class DraftSnapshot:
    """Cached editing draft for an idea."""

    draft_id: int
    idea_id: str
    content: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "draft_id": self.draft_id,
            "idea_id": self.idea_id,
            "content": self.content,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Comment:
    """User or collaborator comment on the current idea version."""

    comment_id: int
    idea_id: str
    version_number: int
    author: str
    topic: str | None
    body: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "comment_id": self.comment_id,
            "idea_id": self.idea_id,
            "version_number": self.version_number,
            "author": self.author,
            "topic": self.topic,
            "body": self.body,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Annotation:
    """User annotation pinned to the current idea version."""

    annotation_id: int
    idea_id: str
    version_number: int
    body: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "annotation_id": self.annotation_id,
            "idea_id": self.idea_id,
            "version_number": self.version_number,
            "body": self.body,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Attachment:
    """Attachment metadata linked to an idea version."""

    attachment_id: int
    idea_id: str
    version_number: int
    label: str
    uri: str
    topic: str | None
    media_type: str | None
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "attachment_id": self.attachment_id,
            "idea_id": self.idea_id,
            "version_number": self.version_number,
            "label": self.label,
            "uri": self.uri,
            "topic": self.topic,
            "media_type": self.media_type,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AgentResearchNote:
    """Research, concern, or recommendation supplied by a coding agent."""

    note_id: int
    idea_id: str
    version_number: int
    topic: str
    body: str
    recommendation: str
    source_url: str | None
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "note_id": self.note_id,
            "idea_id": self.idea_id,
            "version_number": self.version_number,
            "topic": self.topic,
            "body": self.body,
            "recommendation": self.recommendation,
            "source_url": self.source_url,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Relationship:
    """Directed connection between two ideas."""

    relationship_id: int
    source_id: str
    target_id: str
    label: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "relationship_id": self.relationship_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "label": self.label,
        }


@dataclass(frozen=True)
class IdeaDetail:
    """Full idea record for the detail workspace."""

    idea_id: str
    title: str
    brief: str
    status: IdeaStatus
    created_at: str
    updated_at: str
    current_version: IdeaVersion
    history: list[IdeaVersion]
    drafts: list[DraftSnapshot]
    comments: list[Comment]
    annotations: list[Annotation]
    attachments: list[Attachment]
    agent_notes: list[AgentResearchNote]
    relationships: list[Relationship]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "idea_id": self.idea_id,
            "title": self.title,
            "brief": self.brief,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_version": self.current_version.to_dict(),
            "history": [version.to_dict() for version in self.history],
            "drafts": [draft.to_dict() for draft in self.drafts],
            "comments": [comment.to_dict() for comment in self.comments],
            "annotations": [annotation.to_dict() for annotation in self.annotations],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "agent_notes": [note.to_dict() for note in self.agent_notes],
            "relationships": [
                relationship.to_dict() for relationship in self.relationships
            ],
        }


@dataclass(frozen=True)
class GraphNode:
    """Knowledge graph node for one idea."""

    idea_id: str
    title: str
    status: IdeaStatus
    version_number: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "idea_id": self.idea_id,
            "title": self.title,
            "status": self.status.value,
            "version_number": self.version_number,
        }


@dataclass(frozen=True)
class KnowledgeGraph:
    """Knowledge graph containing ideas and explicit relationships."""

    nodes: list[GraphNode]
    edges: list[Relationship]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation."""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }
