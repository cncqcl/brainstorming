"""SQLite persistence for the brainstorm workspace."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import cast
from uuid import uuid4

from brainstorm_tool.exceptions import DatabaseError, NotFoundError, ValidationError
from brainstorm_tool.models import (
    AgentResearchNote,
    Annotation,
    Attachment,
    Comment,
    DraftSnapshot,
    GraphNode,
    IdeaDetail,
    IdeaDraft,
    IdeaDraftStatus,
    IdeaStatus,
    IdeaSummary,
    IdeaVersion,
    KnowledgeGraph,
    Relationship,
)


def _utc_now(now: datetime | None = None) -> str:
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _require_text(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValidationError(f"{field_name} must not be empty")
    return stripped


def _summary_from_content(content: str, limit: int = 120) -> str:
    first_line = content.strip().splitlines()[0] if content.strip() else "Updated idea"
    if len(first_line) <= limit:
        return first_line
    return f"{first_line[: limit - 1]}..."


def _draft_refinement_prompt(draft_id: int) -> str:
    return (
        f"Refine draft {draft_id} using the Brainstorm Tool project skill. "
        "Ask me any needed questions, update the local database when the "
        "refined idea is ready, mark the draft accepted, and tell me to "
        "refresh the dashboard."
    )


def _last_row_id(cursor: sqlite3.Cursor) -> int:
    if cursor.lastrowid is None:
        raise DatabaseError("SQLite did not return a row id")
    return cursor.lastrowid


class BrainstormStore:
    """Manage ideas, versions, drafts, notes, and graph relationships."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the store and create tables when needed.

        Args:
            db_path: SQLite database file path.

        Raises:
            DatabaseError: If schema initialization fails.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                self._create_schema(connection)
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to initialize database") from exc

    def create_idea(
        self,
        title: str,
        brief: str,
        content: str,
        status: IdeaStatus = IdeaStatus.SEED,
    ) -> IdeaDetail:
        """Create an idea with version 1.

        Args:
            title: Human-readable idea title.
            brief: One-line overview shown in lists and history.
            content: Initial version content.
            status: Initial progress status.

        Returns:
            The newly created idea detail.

        Raises:
            ValidationError: If required fields are empty.
            DatabaseError: If SQLite rejects the insert.
        """
        clean_title = _require_text(title, "title")
        clean_brief = _require_text(brief, "brief")
        clean_content = _require_text(content, "content")
        idea_id = uuid4().hex
        created_at = _utc_now()

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO ideas
                        (id, title, brief, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idea_id,
                        clean_title,
                        clean_brief,
                        status.value,
                        created_at,
                        created_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO versions
                        (idea_id, version_number, content, one_line_summary,
                         created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (idea_id, 1, clean_content, clean_brief, created_at),
                )
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to create idea") from exc

        return self.get_idea(idea_id)

    def list_ideas(self) -> list[IdeaSummary]:
        """Return all ideas for the overview list.

        Returns:
            Idea summaries ordered by newest update first.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    i.id,
                    i.title,
                    i.brief,
                    i.status,
                    i.updated_at,
                    COALESCE(MAX(v.version_number), 0) AS version_number
                FROM ideas AS i
                LEFT JOIN versions AS v ON v.idea_id = i.id
                GROUP BY i.id
                ORDER BY i.updated_at DESC, i.title ASC
                """
            ).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def capture_idea_draft(self, raw_message: str, source: str) -> IdeaDraft:
        """Capture a rough idea message before refinement.

        Args:
            raw_message: Natural-language idea text from a user or agent.
            source: Capture source such as dashboard or agent.

        Returns:
            Captured draft with a visible draft id.

        Raises:
            ValidationError: If required fields are empty.
            DatabaseError: If SQLite rejects the insert.
        """
        clean_message = _require_text(raw_message, "raw_message")
        clean_source = _require_text(source, "source")
        timestamp = _utc_now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO idea_drafts
                        (raw_message, source, status, created_at, updated_at,
                         refinement_prompt)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clean_message,
                        clean_source,
                        IdeaDraftStatus.CAPTURED.value,
                        timestamp,
                        timestamp,
                        "pending",
                    ),
                )
                draft_id = _last_row_id(cursor)
                prompt = _draft_refinement_prompt(draft_id)
                connection.execute(
                    """
                    UPDATE idea_drafts
                    SET refinement_prompt = ?
                    WHERE id = ?
                    """,
                    (prompt, draft_id),
                )
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to capture idea draft") from exc
        return self.get_idea_draft(draft_id)

    def list_idea_drafts(self) -> list[IdeaDraft]:
        """Return captured rough idea drafts ordered newest first.

        Returns:
            Captured drafts.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    raw_message,
                    source,
                    status,
                    created_at,
                    updated_at,
                    refinement_prompt,
                    last_refined_at,
                    accepted_idea_id
                FROM idea_drafts
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [self._idea_draft_from_row(row) for row in rows]

    def get_idea_draft(self, draft_id: int) -> IdeaDraft:
        """Return one captured idea draft.

        Args:
            draft_id: Captured draft primary key.

        Returns:
            Matching captured draft.

        Raises:
            NotFoundError: If the draft does not exist.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    raw_message,
                    source,
                    status,
                    created_at,
                    updated_at,
                    refinement_prompt,
                    last_refined_at,
                    accepted_idea_id
                FROM idea_drafts
                WHERE id = ?
                """,
                (draft_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Idea draft {draft_id!r} was not found")
        return self._idea_draft_from_row(row)

    def refinement_prompt(self, draft_id: int) -> str:
        """Mark a captured draft as refining and return its agent prompt.

        Args:
            draft_id: Captured draft primary key.

        Returns:
            Prompt to paste into a coding agent.

        Raises:
            NotFoundError: If the draft does not exist.
            DatabaseError: If SQLite rejects the update.
        """
        timestamp = _utc_now()
        prompt = _draft_refinement_prompt(draft_id)
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE idea_drafts
                    SET status = ?, updated_at = ?, last_refined_at = ?,
                        refinement_prompt = ?
                    WHERE id = ?
                    """,
                    (
                        IdeaDraftStatus.REFINING.value,
                        timestamp,
                        timestamp,
                        prompt,
                        draft_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Idea draft {draft_id!r} was not found")
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to prepare refinement prompt") from exc
        return prompt

    def accept_idea_draft(self, draft_id: int, idea_id: str) -> IdeaDraft:
        """Mark a captured draft as accepted and link it to an idea.

        Args:
            draft_id: Captured draft primary key.
            idea_id: Accepted idea created or updated from the draft.

        Returns:
            Updated captured draft.

        Raises:
            NotFoundError: If the draft or idea does not exist.
            DatabaseError: If SQLite rejects the update.
        """
        self._ensure_idea_exists(idea_id)
        timestamp = _utc_now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE idea_drafts
                    SET status = ?, updated_at = ?, last_refined_at = ?,
                        accepted_idea_id = ?
                    WHERE id = ?
                    """,
                    (
                        IdeaDraftStatus.ACCEPTED.value,
                        timestamp,
                        timestamp,
                        idea_id,
                        draft_id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Idea draft {draft_id!r} was not found")
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to accept idea draft") from exc
        return self.get_idea_draft(draft_id)

    def archive_idea_draft(self, draft_id: int) -> IdeaDraft:
        """Archive a captured draft without accepting it.

        Args:
            draft_id: Captured draft primary key.

        Returns:
            Updated captured draft.

        Raises:
            NotFoundError: If the draft does not exist.
            DatabaseError: If SQLite rejects the update.
        """
        timestamp = _utc_now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE idea_drafts
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (IdeaDraftStatus.ARCHIVED.value, timestamp, draft_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Idea draft {draft_id!r} was not found")
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to archive idea draft") from exc
        return self.get_idea_draft(draft_id)

    def get_idea(self, idea_id: str) -> IdeaDetail:
        """Return one idea with current version and related workspace data.

        Args:
            idea_id: Identifier of the idea to load.

        Returns:
            Full idea detail.

        Raises:
            NotFoundError: If the idea does not exist.
        """
        with self._connect() as connection:
            idea_row = connection.execute(
                """
                SELECT id, title, brief, status, created_at, updated_at
                FROM ideas
                WHERE id = ?
                """,
                (idea_id,),
            ).fetchone()
            if idea_row is None:
                raise NotFoundError(f"Idea {idea_id!r} was not found")

            current_version = self._current_version(connection, idea_id)
            version_number = current_version.version_number
            return IdeaDetail(
                idea_id=cast(str, idea_row["id"]),
                title=cast(str, idea_row["title"]),
                brief=cast(str, idea_row["brief"]),
                status=IdeaStatus(cast(str, idea_row["status"])),
                created_at=cast(str, idea_row["created_at"]),
                updated_at=cast(str, idea_row["updated_at"]),
                current_version=current_version,
                history=self._versions(connection, idea_id),
                drafts=self._drafts(connection, idea_id),
                comments=self._comments(connection, idea_id, version_number),
                annotations=self._annotations(connection, idea_id, version_number),
                attachments=self._attachments(connection, idea_id, version_number),
                agent_notes=self._agent_notes(connection, idea_id, version_number),
                relationships=self._relationships(connection, idea_id),
            )

    def list_history(self, idea_id: str) -> list[IdeaVersion]:
        """Return all versions for an idea.

        Args:
            idea_id: Identifier of the idea to inspect.

        Returns:
            Version history ordered from oldest to newest.

        Raises:
            NotFoundError: If the idea does not exist.
        """
        self._ensure_idea_exists(idea_id)
        with self._connect() as connection:
            return self._versions(connection, idea_id)

    def update_status(self, idea_id: str, status: IdeaStatus) -> IdeaDetail:
        """Update an idea progress status.

        Args:
            idea_id: Identifier of the idea to update.
            status: New idea status.

        Returns:
            Updated idea detail.

        Raises:
            NotFoundError: If the idea does not exist.
            DatabaseError: If SQLite rejects the update.
        """
        timestamp = _utc_now()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE ideas
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status.value, timestamp, idea_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Idea {idea_id!r} was not found")
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to update idea status") from exc
        return self.get_idea(idea_id)

    def save_version(
        self,
        idea_id: str,
        content: str,
        one_line_summary: str | None = None,
    ) -> IdeaDetail:
        """Persist edited content as a new version and clear cached drafts.

        Args:
            idea_id: Identifier of the idea to update.
            content: New version body.
            one_line_summary: Optional one-line history summary.

        Returns:
            Updated idea detail.

        Raises:
            ValidationError: If content is empty.
            NotFoundError: If the idea does not exist.
            DatabaseError: If SQLite rejects the write.
        """
        clean_content = _require_text(content, "content")
        summary = (
            _require_text(one_line_summary, "one_line_summary")
            if one_line_summary is not None
            else _summary_from_content(clean_content)
        )
        timestamp = _utc_now()

        try:
            with self._connect() as connection:
                current = self._current_version(connection, idea_id)
                next_version = current.version_number + 1
                connection.execute(
                    """
                    INSERT INTO versions
                        (idea_id, version_number, content, one_line_summary,
                         created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (idea_id, next_version, clean_content, summary, timestamp),
                )
                connection.execute(
                    "UPDATE ideas SET updated_at = ? WHERE id = ?",
                    (timestamp, idea_id),
                )
                self._clear_drafts(connection, idea_id)
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to save idea version") from exc

        return self.get_idea(idea_id)

    def cache_draft(
        self,
        idea_id: str,
        content: str,
        now: datetime | None = None,
    ) -> DraftSnapshot | None:
        """Cache a distinct editing draft while retaining only five snapshots.

        Args:
            idea_id: Identifier of the idea being edited.
            content: Draft body to cache.
            now: Optional timestamp override for tests.

        Returns:
            The cached draft, or None when content matches the current version
            or latest cached draft.

        Raises:
            NotFoundError: If the idea does not exist.
            DatabaseError: If SQLite rejects the write.
        """
        timestamp = _utc_now(now)
        try:
            with self._connect() as connection:
                current = self._current_version(connection, idea_id)
                last_draft = connection.execute(
                    """
                    SELECT id, idea_id, content, created_at
                    FROM drafts
                    WHERE idea_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (idea_id,),
                ).fetchone()
                if content == current.content:
                    return None
                if last_draft is not None and content == cast(
                    str,
                    last_draft["content"],
                ):
                    return None

                cursor = connection.execute(
                    """
                    INSERT INTO drafts (idea_id, content, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (idea_id, content, timestamp),
                )
                draft_id = _last_row_id(cursor)
                self._trim_drafts(connection, idea_id)
        except sqlite3.Error as exc:
            raise DatabaseError("Failed to cache draft") from exc

        return DraftSnapshot(
            draft_id=draft_id,
            idea_id=idea_id,
            content=content,
            created_at=timestamp,
        )

    def list_drafts(self, idea_id: str) -> list[DraftSnapshot]:
        """Return cached drafts for an idea.

        Args:
            idea_id: Identifier of the idea to inspect.

        Returns:
            Drafts ordered from oldest to newest.

        Raises:
            NotFoundError: If the idea does not exist.
        """
        self._ensure_idea_exists(idea_id)
        with self._connect() as connection:
            return self._drafts(connection, idea_id)

    def clear_drafts(self, idea_id: str) -> None:
        """Remove all cached drafts for an idea.

        Args:
            idea_id: Identifier of the idea to clean up.

        Raises:
            NotFoundError: If the idea does not exist.
        """
        self._ensure_idea_exists(idea_id)
        with self._connect() as connection:
            self._clear_drafts(connection, idea_id)

    def close_editing(self, idea_id: str) -> IdeaDetail:
        """Close editing mode and remove cached drafts.

        Args:
            idea_id: Identifier of the idea whose editing session closed.

        Returns:
            Idea detail after draft cleanup.

        Raises:
            NotFoundError: If the idea does not exist.
        """
        self.clear_drafts(idea_id)
        return self.get_idea(idea_id)

    def add_comment(
        self,
        idea_id: str,
        author: str,
        body: str,
        topic: str | None = None,
    ) -> Comment:
        """Add a comment to the current version of an idea.

        Args:
            idea_id: Identifier of the idea to comment on.
            author: Display name for the commenter.
            body: Comment body.
            topic: Optional comment topic.

        Returns:
            Created comment.
        """
        clean_author = _require_text(author, "author")
        clean_body = _require_text(body, "body")
        clean_topic = topic.strip() if topic and topic.strip() else None
        timestamp = _utc_now()
        with self._connect() as connection:
            current = self._current_version(connection, idea_id)
            cursor = connection.execute(
                """
                INSERT INTO comments
                    (idea_id, version_number, author, topic, body, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    idea_id,
                    current.version_number,
                    clean_author,
                    clean_topic,
                    clean_body,
                    timestamp,
                ),
            )
            comment_id = _last_row_id(cursor)
        return Comment(
            comment_id=comment_id,
            idea_id=idea_id,
            version_number=current.version_number,
            author=clean_author,
            topic=clean_topic,
            body=clean_body,
            created_at=timestamp,
        )

    def add_attachment(
        self,
        idea_id: str,
        label: str,
        uri: str,
        topic: str | None = None,
        media_type: str | None = None,
    ) -> Attachment:
        """Add attachment metadata to the current version of an idea.

        Args:
            idea_id: Identifier of the idea to attach metadata to.
            label: Human-readable attachment label.
            uri: Local path, relative path, or URL for the attachment.
            topic: Optional topic tying the attachment to a discussion.
            media_type: Optional MIME type or media description.

        Returns:
            Created attachment metadata record.
        """
        clean_label = _require_text(label, "label")
        clean_uri = _require_text(uri, "uri")
        clean_topic = topic.strip() if topic and topic.strip() else None
        clean_media_type = (
            media_type.strip() if media_type and media_type.strip() else None
        )
        timestamp = _utc_now()
        with self._connect() as connection:
            current = self._current_version(connection, idea_id)
            cursor = connection.execute(
                """
                INSERT INTO attachments
                    (idea_id, version_number, label, uri, topic, media_type,
                     created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    idea_id,
                    current.version_number,
                    clean_label,
                    clean_uri,
                    clean_topic,
                    clean_media_type,
                    timestamp,
                ),
            )
            attachment_id = _last_row_id(cursor)
        return Attachment(
            attachment_id=attachment_id,
            idea_id=idea_id,
            version_number=current.version_number,
            label=clean_label,
            uri=clean_uri,
            topic=clean_topic,
            media_type=clean_media_type,
            created_at=timestamp,
        )

    def add_annotation(self, idea_id: str, body: str) -> Annotation:
        """Add a user annotation to the current version of an idea.

        Args:
            idea_id: Identifier of the idea to annotate.
            body: Annotation body.

        Returns:
            Created annotation.
        """
        clean_body = _require_text(body, "body")
        timestamp = _utc_now()
        with self._connect() as connection:
            current = self._current_version(connection, idea_id)
            cursor = connection.execute(
                """
                INSERT INTO annotations
                    (idea_id, version_number, body, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (idea_id, current.version_number, clean_body, timestamp),
            )
            annotation_id = _last_row_id(cursor)
        return Annotation(
            annotation_id=annotation_id,
            idea_id=idea_id,
            version_number=current.version_number,
            body=clean_body,
            created_at=timestamp,
        )

    def add_agent_note(
        self,
        idea_id: str,
        topic: str,
        body: str,
        recommendation: str,
        source_url: str | None = None,
    ) -> AgentResearchNote:
        """Add an agent-supplied research note to the current version.

        Args:
            idea_id: Identifier of the idea to annotate.
            topic: Research topic or concern.
            body: Research findings.
            recommendation: Agent recommendation.
            source_url: Optional source URL for the note.

        Returns:
            Created agent research note.
        """
        clean_topic = _require_text(topic, "topic")
        clean_body = _require_text(body, "body")
        clean_recommendation = _require_text(recommendation, "recommendation")
        clean_source = source_url.strip() if source_url else None
        timestamp = _utc_now()
        with self._connect() as connection:
            current = self._current_version(connection, idea_id)
            cursor = connection.execute(
                """
                INSERT INTO agent_notes
                    (idea_id, version_number, topic, body, recommendation,
                     source_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    idea_id,
                    current.version_number,
                    clean_topic,
                    clean_body,
                    clean_recommendation,
                    clean_source,
                    timestamp,
                ),
            )
            note_id = _last_row_id(cursor)
        return AgentResearchNote(
            note_id=note_id,
            idea_id=idea_id,
            version_number=current.version_number,
            topic=clean_topic,
            body=clean_body,
            recommendation=clean_recommendation,
            source_url=clean_source,
            created_at=timestamp,
        )

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        label: str,
    ) -> Relationship:
        """Create a directed relationship between two ideas.

        Args:
            source_id: Source idea identifier.
            target_id: Target idea identifier.
            label: Relationship label.

        Returns:
            Created relationship.

        Raises:
            ValidationError: If the relationship is invalid.
            NotFoundError: If either idea does not exist.
        """
        if source_id == target_id:
            raise ValidationError("source_id and target_id must be different")
        clean_label = _require_text(label, "label")
        self._ensure_idea_exists(source_id)
        self._ensure_idea_exists(target_id)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO relationships (source_id, target_id, label)
                VALUES (?, ?, ?)
                """,
                (source_id, target_id, clean_label),
            )
            relationship_id = _last_row_id(cursor)
        return Relationship(relationship_id, source_id, target_id, clean_label)

    def get_knowledge_graph(self) -> KnowledgeGraph:
        """Return graph nodes and registered idea relationships.

        Returns:
            Knowledge graph data suitable for the dashboard renderer.
        """
        with self._connect() as connection:
            node_rows = connection.execute(
                """
                SELECT
                    i.id,
                    i.title,
                    i.status,
                    COALESCE(MAX(v.version_number), 0) AS version_number
                FROM ideas AS i
                LEFT JOIN versions AS v ON v.idea_id = i.id
                GROUP BY i.id
                ORDER BY i.title ASC
                """
            ).fetchall()
            edge_rows = connection.execute(
                """
                SELECT id, source_id, target_id, label
                FROM relationships
                ORDER BY id ASC
                """
            ).fetchall()

        return KnowledgeGraph(
            nodes=[
                GraphNode(
                    idea_id=cast(str, row["id"]),
                    title=cast(str, row["title"]),
                    status=IdeaStatus(cast(str, row["status"])),
                    version_number=cast(int, row["version_number"]),
                )
                for row in node_rows
            ],
            edges=[self._relationship_from_row(row) for row in edge_rows],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ideas (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                brief TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS versions (
                idea_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                one_line_summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (idea_id, version_number),
                FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE CASCADE
            );

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

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                author TEXT NOT NULL,
                topic TEXT,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (idea_id, version_number)
                    REFERENCES versions(idea_id, version_number)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (idea_id, version_number)
                    REFERENCES versions(idea_id, version_number)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                label TEXT NOT NULL,
                uri TEXT NOT NULL,
                topic TEXT,
                media_type TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (idea_id, version_number)
                    REFERENCES versions(idea_id, version_number)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                topic TEXT NOT NULL,
                body TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                source_url TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (idea_id, version_number)
                    REFERENCES versions(idea_id, version_number)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                label TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES ideas(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES ideas(id) ON DELETE CASCADE
            );

            """
        )

    def _ensure_idea_exists(self, idea_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM ideas WHERE id = ?",
                (idea_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Idea {idea_id!r} was not found")

    def _current_version(
        self,
        connection: sqlite3.Connection,
        idea_id: str,
    ) -> IdeaVersion:
        row = connection.execute(
            """
            SELECT idea_id, version_number, content, one_line_summary, created_at
            FROM versions
            WHERE idea_id = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (idea_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Idea {idea_id!r} was not found")
        return self._version_from_row(row)

    def _versions(
        self,
        connection: sqlite3.Connection,
        idea_id: str,
    ) -> list[IdeaVersion]:
        rows = connection.execute(
            """
            SELECT idea_id, version_number, content, one_line_summary, created_at
            FROM versions
            WHERE idea_id = ?
            ORDER BY version_number ASC
            """,
            (idea_id,),
        ).fetchall()
        return [self._version_from_row(row) for row in rows]

    def _drafts(
        self,
        connection: sqlite3.Connection,
        idea_id: str,
    ) -> list[DraftSnapshot]:
        rows = connection.execute(
            """
            SELECT id, idea_id, content, created_at
            FROM drafts
            WHERE idea_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (idea_id,),
        ).fetchall()
        return [self._draft_from_row(row) for row in rows]

    def _comments(
        self,
        connection: sqlite3.Connection,
        idea_id: str,
        version_number: int,
    ) -> list[Comment]:
        rows = connection.execute(
            """
            SELECT id, idea_id, version_number, author, topic, body, created_at
            FROM comments
            WHERE idea_id = ? AND version_number = ?
            ORDER BY created_at ASC, id ASC
            """,
            (idea_id, version_number),
        ).fetchall()
        return [self._comment_from_row(row) for row in rows]

    def _annotations(
        self,
        connection: sqlite3.Connection,
        idea_id: str,
        version_number: int,
    ) -> list[Annotation]:
        rows = connection.execute(
            """
            SELECT id, idea_id, version_number, body, created_at
            FROM annotations
            WHERE idea_id = ? AND version_number = ?
            ORDER BY created_at ASC, id ASC
            """,
            (idea_id, version_number),
        ).fetchall()
        return [self._annotation_from_row(row) for row in rows]

    def _attachments(
        self,
        connection: sqlite3.Connection,
        idea_id: str,
        version_number: int,
    ) -> list[Attachment]:
        rows = connection.execute(
            """
            SELECT
                id,
                idea_id,
                version_number,
                label,
                uri,
                topic,
                media_type,
                created_at
            FROM attachments
            WHERE idea_id = ? AND version_number = ?
            ORDER BY created_at ASC, id ASC
            """,
            (idea_id, version_number),
        ).fetchall()
        return [self._attachment_from_row(row) for row in rows]

    def _agent_notes(
        self,
        connection: sqlite3.Connection,
        idea_id: str,
        version_number: int,
    ) -> list[AgentResearchNote]:
        rows = connection.execute(
            """
            SELECT
                id,
                idea_id,
                version_number,
                topic,
                body,
                recommendation,
                source_url,
                created_at
            FROM agent_notes
            WHERE idea_id = ? AND version_number = ?
            ORDER BY created_at ASC, id ASC
            """,
            (idea_id, version_number),
        ).fetchall()
        return [self._agent_note_from_row(row) for row in rows]

    def _relationships(
        self,
        connection: sqlite3.Connection,
        idea_id: str,
    ) -> list[Relationship]:
        rows = connection.execute(
            """
            SELECT id, source_id, target_id, label
            FROM relationships
            WHERE source_id = ? OR target_id = ?
            ORDER BY id ASC
            """,
            (idea_id, idea_id),
        ).fetchall()
        return [self._relationship_from_row(row) for row in rows]

    def _trim_drafts(self, connection: sqlite3.Connection, idea_id: str) -> None:
        rows = connection.execute(
            """
            SELECT id
            FROM drafts
            WHERE idea_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (idea_id,),
        ).fetchall()
        stale_ids = [cast(int, row["id"]) for row in rows[5:]]
        if stale_ids:
            self._delete_draft_ids(connection, stale_ids)

    def _delete_draft_ids(
        self,
        connection: sqlite3.Connection,
        draft_ids: Iterable[int],
    ) -> None:
        connection.executemany(
            "DELETE FROM drafts WHERE id = ?",
            [(draft_id,) for draft_id in draft_ids],
        )

    def _clear_drafts(self, connection: sqlite3.Connection, idea_id: str) -> None:
        connection.execute("DELETE FROM drafts WHERE idea_id = ?", (idea_id,))

    def _summary_from_row(self, row: sqlite3.Row) -> IdeaSummary:
        return IdeaSummary(
            idea_id=cast(str, row["id"]),
            title=cast(str, row["title"]),
            brief=cast(str, row["brief"]),
            status=IdeaStatus(cast(str, row["status"])),
            version_number=cast(int, row["version_number"]),
            updated_at=cast(str, row["updated_at"]),
        )

    def _version_from_row(self, row: sqlite3.Row) -> IdeaVersion:
        return IdeaVersion(
            idea_id=cast(str, row["idea_id"]),
            version_number=cast(int, row["version_number"]),
            content=cast(str, row["content"]),
            one_line_summary=cast(str, row["one_line_summary"]),
            created_at=cast(str, row["created_at"]),
        )

    def _draft_from_row(self, row: sqlite3.Row) -> DraftSnapshot:
        return DraftSnapshot(
            draft_id=cast(int, row["id"]),
            idea_id=cast(str, row["idea_id"]),
            content=cast(str, row["content"]),
            created_at=cast(str, row["created_at"]),
        )

    def _idea_draft_from_row(self, row: sqlite3.Row) -> IdeaDraft:
        return IdeaDraft(
            draft_id=cast(int, row["id"]),
            raw_message=cast(str, row["raw_message"]),
            source=cast(str, row["source"]),
            status=IdeaDraftStatus(cast(str, row["status"])),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
            refinement_prompt=cast(str, row["refinement_prompt"]),
            last_refined_at=cast(str | None, row["last_refined_at"]),
            accepted_idea_id=cast(str | None, row["accepted_idea_id"]),
        )

    def _comment_from_row(self, row: sqlite3.Row) -> Comment:
        return Comment(
            comment_id=cast(int, row["id"]),
            idea_id=cast(str, row["idea_id"]),
            version_number=cast(int, row["version_number"]),
            author=cast(str, row["author"]),
            topic=cast(str | None, row["topic"]),
            body=cast(str, row["body"]),
            created_at=cast(str, row["created_at"]),
        )

    def _annotation_from_row(self, row: sqlite3.Row) -> Annotation:
        return Annotation(
            annotation_id=cast(int, row["id"]),
            idea_id=cast(str, row["idea_id"]),
            version_number=cast(int, row["version_number"]),
            body=cast(str, row["body"]),
            created_at=cast(str, row["created_at"]),
        )

    def _attachment_from_row(self, row: sqlite3.Row) -> Attachment:
        return Attachment(
            attachment_id=cast(int, row["id"]),
            idea_id=cast(str, row["idea_id"]),
            version_number=cast(int, row["version_number"]),
            label=cast(str, row["label"]),
            uri=cast(str, row["uri"]),
            topic=cast(str | None, row["topic"]),
            media_type=cast(str | None, row["media_type"]),
            created_at=cast(str, row["created_at"]),
        )

    def _agent_note_from_row(self, row: sqlite3.Row) -> AgentResearchNote:
        return AgentResearchNote(
            note_id=cast(int, row["id"]),
            idea_id=cast(str, row["idea_id"]),
            version_number=cast(int, row["version_number"]),
            topic=cast(str, row["topic"]),
            body=cast(str, row["body"]),
            recommendation=cast(str, row["recommendation"]),
            source_url=cast(str | None, row["source_url"]),
            created_at=cast(str, row["created_at"]),
        )

    def _relationship_from_row(self, row: sqlite3.Row) -> Relationship:
        return Relationship(
            relationship_id=cast(int, row["id"]),
            source_id=cast(str, row["source_id"]),
            target_id=cast(str, row["target_id"]),
            label=cast(str, row["label"]),
        )
