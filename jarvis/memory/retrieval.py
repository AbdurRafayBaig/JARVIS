"""Memory Retriever

Provides RAG-style retrieval for agent context.
"""

from typing import Optional
from loguru import logger

from jarvis.memory.conversation_memory import ConversationMemory
from jarvis.memory.project_memory import ProjectMemory
from jarvis.memory.vector_store import VectorStore, get_vector_store


class MemoryRetriever:
    """Retrieves relevant context from memory for agent planning."""

    def __init__(self):
        self.conversation = ConversationMemory()
        self.project = ProjectMemory()
        self.vector_store = get_vector_store()

    async def get_context(
        self,
        query: str,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
        max_tokens: int = 4000,
    ) -> dict:
        """Get relevant context for a query."""
        context = {
            "conversation_history": [],
            "project_info": None,
            "similar_documents": [],
            "preferences": {},
        }

        try:
            history = await self.conversation.get_history(task_id=task_id, limit=10)
            context["conversation_history"] = [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in history
            ]
        except Exception as e:
            logger.warning(f"Failed to get conversation history: {e}")

        if project_id:
            try:
                project = await self.project.get_project(project_id)
                if project:
                    context["project_info"] = {
                        "name": project.name,
                        "path": project.path,
                        "description": project.description,
                        "language": project.language,
                        "framework": project.framework,
                        "github_repo": project.github_repo,
                    }
            except Exception as e:
                logger.warning(f"Failed to get project info: {e}")

        try:
            context["preferences"] = await self.project.list_preferences()
        except Exception as e:
            logger.warning(f"Failed to get preferences: {e}")

        try:
            similar = await self.vector_store.search(query, top_k=5)
            context["similar_documents"] = [
                {"text": entry.text, "score": score, "metadata": entry.metadata}
                for entry, score in similar
            ]
        except Exception as e:
            logger.warning(f"Failed to search vector store: {e}")

        return context

    async def add_knowledge(
        self,
        text: str,
        metadata: Optional[dict] = None,
        source: str = "manual",
    ) -> None:
        """Add knowledge to the vector store."""
        import hashlib
        entry_id = hashlib.sha256(text.encode()).hexdigest()[:16]

        from jarvis.memory.vector_store import VectorEntry
        entry = VectorEntry(
            id=entry_id,
            text=text,
            embedding=[],
            metadata={"source": source, **(metadata or {})},
        )

        await self.vector_store.add(entry)
        logger.debug(f"Added knowledge: {entry_id} ({source})")

    async def add_conversation_to_knowledge(self) -> None:
        """Index recent conversation history into vector store."""
        messages = await self.conversation.get_recent(count=50)

        for msg in messages:
            if msg.role == "user":
                await self.add_knowledge(
                    text=msg.content,
                    metadata={
                        "role": msg.role,
                        "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                    },
                    source="conversation",
                )
