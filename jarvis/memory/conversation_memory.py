"""Conversation Memory

Stores and retrieves conversation history from the database.
"""

import uuid
from typing import Optional

from sqlalchemy import select, desc, delete
from loguru import logger

from jarvis.core.database import get_session
from jarvis.core.models import Conversation

# Session shared by every ConversationMemory created without an explicit id,
# so a single JARVIS run groups into one conversation thread.
_DEFAULT_SESSION_ID = str(uuid.uuid4())


def get_default_session_id() -> str:
    """Session id used for this JARVIS process."""
    return _DEFAULT_SESSION_ID


class ConversationMemory:
    """Manages conversation history storage."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or _DEFAULT_SESSION_ID

    async def store(
        self,
        role: str,
        content: str,
        task_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Conversation]:
        """Store a conversation message."""
        try:
            async with get_session() as session:
                message = Conversation(
                    session_id=session_id or self.session_id,
                    role=role,
                    content=content,
                    task_id=task_id,
                    task_metadata=metadata or {},
                )
                session.add(message)
                await session.commit()
                await session.refresh(message)
                logger.debug(f"Stored conversation: {role} - {content[:50]}...")
                return message
        except Exception as e:
            logger.error(f"Failed to store conversation message: {e}")
            return None

    async def get_history(
        self,
        task_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        session_id: Optional[str] = None,
    ) -> list[Conversation]:
        """Get conversation history in chronological order."""
        async with get_session() as session:
            query = select(Conversation).order_by(desc(Conversation.created_at))

            if task_id:
                query = query.where(Conversation.task_id == task_id)
            if session_id:
                query = query.where(Conversation.session_id == session_id)

            query = query.offset(offset).limit(limit)
            result = await session.execute(query)
            messages = result.scalars().all()
            return list(reversed(messages))

    async def get_recent(self, count: int = 10) -> list[Conversation]:
        """Get recent messages from the current session."""
        return await self.get_history(limit=count, session_id=self.session_id)

    async def get_llm_messages(self, count: int = 10) -> list[dict[str, str]]:
        """Get recent history shaped for an LLM prompt."""
        messages = await self.get_recent(count=count)
        return [{"role": m.role, "content": m.content} for m in messages]

    async def clear(
        self,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Clear conversation history."""
        async with get_session() as session:
            stmt = delete(Conversation)
            if task_id:
                stmt = stmt.where(Conversation.task_id == task_id)
            if session_id:
                stmt = stmt.where(Conversation.session_id == session_id)

            result = await session.execute(stmt)
            await session.commit()
            count = result.rowcount or 0
            logger.info(f"Cleared {count} conversation messages")
            return count

    async def search(self, query: str, limit: int = 10) -> list[Conversation]:
        """Search conversation history by content."""
        async with get_session() as session:
            stmt = (
                select(Conversation)
                .where(Conversation.content.contains(query))
                .order_by(desc(Conversation.created_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
