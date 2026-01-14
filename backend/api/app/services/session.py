"""
Session management for multi-turn conversations.

Provides Redis-backed session storage for tracking conversation state,
message history, and accumulated search filters across multiple exchanges.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.core.cache import CacheService

logger = logging.getLogger(__name__)

# Session TTL: 1 hour of inactivity
SESSION_TTL_SECONDS = 3600


class SessionMessage(BaseModel):
    """A single message in the conversation history."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = None

    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.now(UTC)
        super().__init__(**data)


class SearchFilter(BaseModel):
    """A search filter applied in the session."""

    column: str
    operator: str
    value: Any


class SessionState(BaseModel):
    """
    Complete state for a search session.

    Tracks conversation history, accumulated filters, and results
    to enable multi-turn refinement of searches.
    """

    session_id: str
    created_at: datetime
    updated_at: datetime

    # Conversation history (for context in multi-turn)
    messages: list[SessionMessage] = []

    # pydantic-ai message history (internal format for agent)
    agent_messages: list[dict] = []

    # Accumulated filters from all turns
    filters: list[SearchFilter] = []

    # Last search results (summary, not full data)
    last_result_count: int = 0
    last_query: str = ""

    def add_user_message(self, content: str):
        """Add a user message to history."""
        self.messages.append(SessionMessage(role="user", content=content))
        self.updated_at = datetime.now(UTC)

    def add_assistant_message(self, content: str):
        """Add an assistant message to history."""
        self.messages.append(SessionMessage(role="assistant", content=content))
        self.updated_at = datetime.now(UTC)

    def update_filters(self, new_filters: list[SearchFilter]):
        """Update the accumulated filters."""
        self.filters = new_filters
        self.updated_at = datetime.now(UTC)

    def clear_filters(self):
        """Clear all filters (start fresh)."""
        self.filters = []
        self.updated_at = datetime.now(UTC)

    def get_context_summary(self) -> str:
        """Get a summary of current state for the agent."""
        if not self.filters:
            return "No filters currently applied."

        filter_desc = []
        for f in self.filters:
            filter_desc.append(f"{f.column} {f.operator} {f.value}")

        return (
            f"Current filters: {', '.join(filter_desc)}. "
            f"Last search returned {self.last_result_count} results."
        )


class SessionService:
    """
    Service for managing conversation sessions.

    Uses Redis for persistence with automatic expiration.
    """

    def __init__(self, cache: CacheService):
        self.cache = cache

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for a session."""
        return f"session:{session_id}"

    async def create_session(self) -> SessionState:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        session = SessionState(
            session_id=session_id,
            created_at=now,
            updated_at=now,
        )

        await self._save_session(session)
        logger.info(f"Created new session: {session_id}")
        return session

    async def get_session(self, session_id: str) -> SessionState | None:
        """Get an existing session by ID."""
        key = self._session_key(session_id)
        data = await self.cache.get(key)

        if data is None:
            logger.debug(f"Session not found: {session_id}")
            return None

        try:
            session = SessionState(**data)
            return session
        except Exception as e:
            logger.error(f"Failed to deserialize session {session_id}: {e}")
            return None

    async def get_or_create_session(self, session_id: str | None) -> SessionState:
        """Get existing session or create new one."""
        if session_id:
            session = await self.get_session(session_id)
            if session:
                return session
            logger.info(f"Session {session_id} not found, creating new one")

        return await self.create_session()

    async def _save_session(self, session: SessionState):
        """Save session to Redis."""
        key = self._session_key(session.session_id)

        # Convert to dict, handling datetime serialization
        data = session.model_dump(mode="json")

        await self.cache.set(key, data, ttl=SESSION_TTL_SECONDS)

    async def update_session(self, session: SessionState):
        """Update an existing session."""
        session.updated_at = datetime.now(UTC)
        await self._save_session(session)

    async def delete_session(self, session_id: str):
        """Delete a session."""
        key = self._session_key(session_id)
        await self.cache.delete(key)
        logger.info(f"Deleted session: {session_id}")

    async def extend_session(self, session_id: str):
        """Extend session TTL without modifying content."""
        session = await self.get_session(session_id)
        if session:
            await self._save_session(session)


# Singleton instance
_session_service: SessionService | None = None


async def get_session_service() -> SessionService:
    """Get the session service singleton."""
    global _session_service
    if _session_service is None:
        from app.core.dependencies import get_cache_service

        cache = await get_cache_service()
        _session_service = SessionService(cache)
        logger.info("Session service initialized")
    return _session_service


def reset_session_service():
    """Reset the session service singleton (for testing/shutdown)."""
    global _session_service
    _session_service = None
