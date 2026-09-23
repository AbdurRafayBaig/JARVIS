"""Vector Store

Provides embeddings-based semantic search.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
import numpy as np
from loguru import logger

from jarvis.core.config import get_settings


@dataclass
class VectorEntry:
    """A vector store entry."""
    id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "embedding": self.embedding,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorEntry":
        return cls(
            id=data["id"],
            text=data.get("text", ""),
            embedding=data.get("embedding") or [],
            metadata=data.get("metadata") or {},
        )


def _cache_key(text: str) -> str:
    """Stable key for an embedding cache entry.

    Hashing the whole text, rather than slicing a prefix, keeps two long
    passages that share an opening from colliding onto one embedding.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class VectorStore:
    """Simple vector store for semantic search."""

    def __init__(self):
        self._settings = get_settings()
        self._entries: list[VectorEntry] = []
        self._embeddings_cache: dict[str, list[float]] = {}
        data_dir = Path(self._settings.get_data_dir())
        self._cache_file = data_dir / "embeddings_cache.json"
        self._entries_file = data_dir / "vector_entries.json"
        self._dirty = False
        self._load_cache()
        self._load_entries()

    # -- persistence ---------------------------------------------------------

    def _load_cache(self) -> None:
        """Load embeddings cache from disk."""
        if not self._cache_file.exists():
            return
        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._embeddings_cache = data.get("embeddings", {})
            logger.debug(f"Loaded {len(self._embeddings_cache)} cached embeddings")
        except Exception as e:
            logger.warning(f"Failed to load embeddings cache: {e}")

    def _load_entries(self) -> None:
        """Load stored entries from disk.

        Without this the store was rebuilt empty on every start, so anything
        indexed in an earlier session was unreachable.
        """
        if not self._entries_file.exists():
            return
        try:
            with open(self._entries_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = [VectorEntry.from_dict(e) for e in data.get("entries", [])]
            logger.debug(f"Loaded {len(self._entries)} vector entries")
        except Exception as e:
            logger.warning(f"Failed to load vector entries: {e}")

    def _save_cache(self) -> None:
        """Save embeddings cache and entries to disk."""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump({"embeddings": self._embeddings_cache}, f)
        except Exception as e:
            logger.warning(f"Failed to save embeddings cache: {e}")

        self._save_entries()

    def _save_entries(self) -> None:
        """Persist entries so indexed knowledge survives a restart."""
        if not self._dirty:
            return
        try:
            self._entries_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._entries_file, "w", encoding="utf-8") as f:
                json.dump({"entries": [e.to_dict() for e in self._entries]}, f)
            self._dirty = False
        except Exception as e:
            logger.warning(f"Failed to save vector entries: {e}")

    def save(self) -> None:
        """Flush the store to disk."""
        self._save_cache()

    # -- embeddings ----------------------------------------------------------

    async def get_embedding(self, text: str) -> list[float]:
        """Get an embedding for text using the configured provider."""
        key = _cache_key(text)
        if key in self._embeddings_cache:
            return self._embeddings_cache[key]

        try:
            from jarvis.llm.manager import get_llm_manager

            provider = get_llm_manager().get_provider()

            # The provider API is embeddings(texts) -> EmbeddingResponse.
            response = await provider.embeddings([text])
            embedding = response.embeddings[0] if response.embeddings else []

            if not embedding:
                logger.warning(
                    f"Provider {provider.__class__.__name__} returned no embedding; "
                    f"semantic search will skip this entry."
                )
                return []

            self._embeddings_cache[key] = embedding
            if len(self._embeddings_cache) % 10 == 0:
                self._save_cache()

            return embedding
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return []

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0

        a_arr = np.array(a)
        b_arr = np.array(b)

        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))

    # -- store ---------------------------------------------------------------

    async def add(self, entry: VectorEntry) -> None:
        """Add an entry to the store, replacing any entry with the same id."""
        if not entry.embedding or all(x == 0 for x in entry.embedding):
            entry.embedding = await self.get_embedding(entry.text)

        for i, existing in enumerate(self._entries):
            if existing.id == entry.id:
                self._entries[i] = entry
                break
        else:
            self._entries.append(entry)

        self._dirty = True
        self._save_entries()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> list[tuple[VectorEntry, float]]:
        """Search for similar entries."""
        query_embedding = await self.get_embedding(query)
        if not query_embedding:
            return []

        results = []
        for entry in self._entries:
            if not entry.embedding:
                continue
            similarity = self.cosine_similarity(query_embedding, entry.embedding)
            if similarity >= threshold:
                results.append((entry, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get_entry(self, entry_id: str) -> Optional[VectorEntry]:
        """Get an entry by ID."""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    def remove(self, entry_id: str) -> bool:
        """Remove an entry by ID."""
        for i, entry in enumerate(self._entries):
            if entry.id == entry_id:
                self._entries.pop(i)
                self._dirty = True
                self._save_entries()
                return True
        return False

    @property
    def count(self) -> int:
        """Number of stored entries."""
        return len(self._entries)

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        self._embeddings_cache.clear()
        self._dirty = False
        for path in (self._cache_file, self._entries_file):
            if path.exists():
                path.unlink()


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
