"""Async SQLAlchemy engine and session factory.

Uses SQLite + aiosqlite with WAL mode and foreign keys ON.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from bot.db.models import Base


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
