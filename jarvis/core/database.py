"""JARVIS Database Layer"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from jarvis.core.config import get_settings
from jarvis.core.logging import get_logger, log_exception

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Database:
    """Database manager for JARVIS."""

    def __init__(self, db_path: Optional[Path] = None):
        self.settings = get_settings()
        self.db_path = db_path or self.settings.get_db_path()
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_engine = None
        self._async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._sync_session_factory: Optional[sessionmaker] = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Whether initialize() has created the schema for this instance."""
        return self._initialized

    @property
    def async_engine(self) -> AsyncEngine:
        if self._async_engine is None:
            self._async_engine = self._create_async_engine()
        return self._async_engine

    @property
    def sync_engine(self):
        if self._sync_engine is None:
            self._sync_engine = self._create_sync_engine()
        return self._sync_engine

    def _create_async_engine(self) -> AsyncEngine:
        """Create async engine for SQLite."""
        url = f"sqlite+aiosqlite:///{self.db_path}"
        engine = create_async_engine(
            url,
            echo=False,
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
            },
        )
        return engine

    def _create_sync_engine(self):
        """Create sync engine for migrations."""
        url = f"sqlite:///{self.db_path}"
        engine = create_engine(
            url,
            echo=False,
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
            },
        )
        return engine

    @property
    def async_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._async_session_factory

    @property
    def sync_session_factory(self) -> sessionmaker:
        if self._sync_session_factory is None:
            self._sync_session_factory = sessionmaker(
                self.sync_engine,
                expire_on_commit=False,
            )
        return self._sync_session_factory

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session."""
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    def sync_session(self):
        """Get a sync database session (context manager)."""
        session = self.sync_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def initialize(self) -> None:
        """Initialize database tables."""
        logger.info(f"Initializing database at {self.db_path}")

        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await self._enable_wal_mode()
        self._initialized = True
        logger.info("Database initialized successfully")

    async def _enable_wal_mode(self) -> None:
        """Enable WAL mode for better concurrency."""
        async with self.async_engine.connect() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA cache_size=-32768"))
            await conn.execute(text("PRAGMA temp_store=MEMORY"))
            await conn.commit()

    async def close(self) -> None:
        """Close database connections."""
        if self._async_engine:
            await self._async_engine.dispose()
            self._async_engine = None
        if self._sync_engine:
            self._sync_engine.dispose()
            self._sync_engine = None
        self._initialized = False
        logger.info("Database connections closed")

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            log_exception(e, "database health check")
            return False

    def get_sync_session(self):
        """Get a synchronous session for non-async contexts."""
        return self.sync_session_factory()


_database: Optional[Database] = None


def get_database() -> Database:
    """Get global database instance."""
    global _database
    if _database is None:
        _database = Database()
    return _database


async def init_database() -> Database:
    """Initialize and return database instance."""
    db = get_database()
    await db.initialize()
    return db


async def close_database() -> None:
    """Close global database instance."""
    global _database
    if _database:
        await _database.close()
        _database = None


def is_database_ready() -> bool:
    """Whether a database has been initialized in this process.

    Subsystems that persist opportunistically (memory, audit, task history)
    check this so they stay inert when JARVIS runs without a database --
    for example inside unit tests.
    """
    return _database is not None and _database.is_initialized


@asynccontextmanager
async def get_session():
    """Get an async database session."""
    db = get_database()
    async with db.session() as session:
        yield session