"""Async SQLAlchemy engine and session factory.

Uses SQLite + aiosqlite with WAL mode and foreign keys ON.
"""

from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from bot.db.models import Base

# ---------------------------------------------------------------------------
# Global session factory reference — set once at startup by bot/main.py
# Handlers import get_session_factory() to create ad-hoc sessions.
# ---------------------------------------------------------------------------
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def set_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Store the session factory globally so handlers can use it."""
    global _session_factory
    _session_factory = factory


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global session factory.

    Raises:
        RuntimeError: If set_session_factory() was not called yet.
    """
    if _session_factory is None:
        raise RuntimeError(
            "session_factory is not set. Call set_session_factory() at startup."
        )
    return _session_factory


def create_engine(db_path: str) -> AsyncEngine:
    """Create async engine with aiosqlite driver, WAL mode, foreign keys ON."""
    engine = create_async_engine(
        db_path,
        echo=False,
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return async_sessionmaker bound to engine. expire_on_commit=False."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-style dependency: yield session, close on exit."""
    async with session_factory() as session:
        yield session


async def init_db(engine: AsyncEngine) -> None:
    """Create all tables from Base.metadata. Call once at startup."""
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session_direct(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_session - used by scheduler."""
    async with session_factory() as session:
        yield session
