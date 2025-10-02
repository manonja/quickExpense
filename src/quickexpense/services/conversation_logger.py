"""Conversation history logging for multi-agent systems."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from quickexpense.services.agents import AgentResult, MultiAgentReceiptResponse

logger = logging.getLogger(__name__)


class ConversationEntry(BaseModel):
    """Individual conversation entry in the history."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str
    session_id: str | None = None
    agent_name: str
    role: str  # user, assistant, system
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float | None = None
    processing_time: float | None = None


class ConversationHistory(BaseModel):
    """Complete conversation history for a session."""

    correlation_id: str
    session_id: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    entries: list[ConversationEntry] = Field(default_factory=list)
    final_result: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationLogger:
    """SQLite-based conversation history logger."""

    def __init__(self, db_path: Path | None = None):
        """Initialize conversation logger."""
        self.db_path = db_path or Path("data/conversation_history.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT NOT NULL,
                    session_id TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    final_result TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(correlation_id)
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT NOT NULL,
                    session_id TEXT,
                    timestamp TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence_score REAL,
                    processing_time REAL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (correlation_id) REFERENCES conversations(correlation_id)
                )
            """
            )

            # Indexes for performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_correlation_id "
                "ON conversation_entries(correlation_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_session_id "
                "ON conversation_entries(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp "
                "ON conversation_entries(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_name "
                "ON conversation_entries(agent_name)"
            )

            conn.commit()

    def start_conversation(
        self,
        correlation_id: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Start logging a new conversation."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO conversations
                    (correlation_id, session_id, start_time, metadata)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        correlation_id,
                        session_id,
                        datetime.now(UTC).isoformat(),
                        json.dumps(metadata or {}),
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # Conversation already exists, update start time
                conn.execute(
                    """
                    UPDATE conversations
                    SET start_time = ?, session_id = ?
                    WHERE correlation_id = ?
                    """,
                    (
                        datetime.now(UTC).isoformat(),
                        session_id,
                        correlation_id,
                    ),
                )
                conn.commit()

    def log_agent_message(
        self,
        correlation_id: str,
        agent_name: str,
        content: str,
        role: str = "assistant",
        confidence_score: float | None = None,
        processing_time: float | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> None:
        """Log a single agent message."""
        entry = ConversationEntry(
            correlation_id=correlation_id,
            session_id=session_id,
            agent_name=agent_name,
            role=role,
            content=content,
            confidence_score=confidence_score,
            processing_time=processing_time,
            metadata=metadata or {},
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversation_entries
                (correlation_id, session_id, timestamp, agent_name, role,
                 content, confidence_score, processing_time, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.correlation_id,
                    entry.session_id,
                    entry.timestamp.isoformat(),
                    entry.agent_name,
                    entry.role,
                    entry.content,
                    entry.confidence_score,
                    entry.processing_time,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()

    def log_user_input(
        self,
        correlation_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> None:
        """Log user input message."""
        self.log_agent_message(
            correlation_id=correlation_id,
            agent_name="user",
            content=content,
            role="user",
            metadata=metadata,
            session_id=session_id,
        )

    def log_system_message(
        self,
        correlation_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> None:
        """Log system message."""
        self.log_agent_message(
            correlation_id=correlation_id,
            agent_name="system",
            content=content,
            role="system",
            metadata=metadata,
            session_id=session_id,
        )

    def log_agent_result(
        self,
        correlation_id: str,
        agent_result: AgentResult,
        session_id: str | None = None,
    ) -> None:
        """Log an agent result with full context."""
        # Log the main result
        self.log_agent_message(
            correlation_id=correlation_id,
            agent_name=agent_result.agent_name,
            content=json.dumps(agent_result.data or {}, default=str),
            role="assistant",
            confidence_score=agent_result.confidence_score,
            processing_time=agent_result.processing_time,
            metadata={
                "success": agent_result.success,
                "error": agent_result.error_message,
                **agent_result.metadata,
            },
            session_id=session_id,
        )

    def end_conversation(
        self,
        correlation_id: str,
        final_result: MultiAgentReceiptResponse | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End a conversation and store final results."""
        end_time = datetime.now(UTC).isoformat()

        final_data = None
        if final_result:
            final_data = {
                "success": final_result.success,
                "overall_confidence": final_result.overall_confidence,
                "consensus_method": final_result.consensus_method,
                "processing_time": final_result.processing_time,
                "final_data": final_result.full_data,
                "flags_for_review": final_result.flags_for_review,
                "agent_count": len(final_result.agent_results),
            }

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE conversations
                SET end_time = ?, final_result = ?, metadata = ?
                WHERE correlation_id = ?
                """,
                (
                    end_time,
                    json.dumps(final_data) if final_data else None,
                    json.dumps(metadata or {}),
                    correlation_id,
                ),
            )
            conn.commit()

    def get_conversation(self, correlation_id: str) -> ConversationHistory | None:
        """Retrieve a complete conversation by correlation ID."""
        with sqlite3.connect(self.db_path) as conn:
            # Get conversation metadata
            cursor = conn.execute(
                """
                SELECT session_id, start_time, end_time, final_result, metadata
                FROM conversations
                WHERE correlation_id = ?
                """,
                (correlation_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            session_id, start_time, end_time, final_result, metadata = row

            # Get all entries
            cursor = conn.execute(
                """
                SELECT timestamp, agent_name, role, content,
                       confidence_score, processing_time, metadata
                FROM conversation_entries
                WHERE correlation_id = ?
                ORDER BY timestamp
                """,
                (correlation_id,),
            )

            entries = []
            for row in cursor:
                entries.append(
                    ConversationEntry(
                        correlation_id=correlation_id,
                        session_id=session_id,
                        timestamp=datetime.fromisoformat(row[0]),
                        agent_name=row[1],
                        role=row[2],
                        content=row[3],
                        confidence_score=row[4],
                        processing_time=row[5],
                        metadata=json.loads(row[6]) if row[6] else {},
                    )
                )

            return ConversationHistory(
                correlation_id=correlation_id,
                session_id=session_id,
                start_time=datetime.fromisoformat(start_time),
                end_time=datetime.fromisoformat(end_time) if end_time else None,
                entries=entries,
                final_result=json.loads(final_result) if final_result else None,
                metadata=json.loads(metadata) if metadata else {},
            )

    def get_recent_conversations(
        self,
        limit: int = 10,
        agent_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent conversations with optional filtering."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT DISTINCT c.correlation_id, c.session_id,
                       c.start_time, c.end_time,
                       COUNT(ce.id) as entry_count,
                       AVG(ce.confidence_score) as avg_confidence
                FROM conversations c
                LEFT JOIN conversation_entries ce
                    ON c.correlation_id = ce.correlation_id
            """

            params = []
            if agent_name:
                query += " WHERE ce.agent_name = ?"
                params.append(agent_name)

            query += """
                GROUP BY c.correlation_id
                ORDER BY c.start_time DESC
                LIMIT ?
            """
            params.append(limit)

            cursor = conn.execute(query, params)

            conversations = []
            for row in cursor:
                conversations.append(
                    {
                        "correlation_id": row[0],
                        "session_id": row[1],
                        "start_time": row[2],
                        "end_time": row[3],
                        "entry_count": row[4],
                        "avg_confidence": row[5],
                    }
                )

            return conversations

    def search_conversations(
        self,
        search_term: str,
        agent_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Search conversations by content or metadata."""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT DISTINCT c.correlation_id, c.start_time,
                       ce.agent_name, ce.content, ce.confidence_score
                FROM conversations c
                JOIN conversation_entries ce
                    ON c.correlation_id = ce.correlation_id
                WHERE ce.content LIKE ?
            """

            params = [f"%{search_term}%"]

            if agent_name:
                query += " AND ce.agent_name = ?"
                params.append(agent_name)

            if start_date:
                query += " AND ce.timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND ce.timestamp <= ?"
                params.append(end_date.isoformat())

            query += " ORDER BY ce.timestamp DESC LIMIT 100"

            cursor = conn.execute(query, params)

            results = []
            for row in cursor:
                results.append(
                    {
                        "correlation_id": row[0],
                        "start_time": row[1],
                        "agent_name": row[2],
                        "content": row[3],
                        "confidence_score": row[4],
                    }
                )

            return results

    def get_conversation_stats(self) -> dict[str, Any]:
        """Get overall conversation statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Total conversations
            total_conversations = conn.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]

            # Average confidence by agent
            cursor = conn.execute(
                """
                SELECT agent_name,
                       AVG(confidence_score) as avg_confidence,
                       COUNT(*) as message_count,
                       AVG(processing_time) as avg_processing_time
                FROM conversation_entries
                WHERE role = 'assistant' AND confidence_score IS NOT NULL
                GROUP BY agent_name
            """
            )

            agent_stats = {}
            for row in cursor:
                agent_stats[row[0]] = {
                    "avg_confidence": row[1],
                    "message_count": row[2],
                    "avg_processing_time": row[3],
                }

            # Success rate
            successful = conn.execute(
                """
                SELECT COUNT(*) FROM conversations
                WHERE final_result IS NOT NULL
                AND json_extract(final_result, '$.success') = 1
            """
            ).fetchone()[0]

            return {
                "total_conversations": total_conversations,
                "successful_conversations": successful,
                "success_rate": (
                    successful / total_conversations if total_conversations > 0 else 0
                ),
                "agent_stats": agent_stats,
            }


# Factory function
def create_conversation_logger(db_path: Path | None = None) -> ConversationLogger:
    """Create a conversation logger instance."""
    return ConversationLogger(db_path=db_path)
