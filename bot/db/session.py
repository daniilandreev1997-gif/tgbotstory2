"""Database session management — SQLite via aiosqlite."""

from __future__ import annotations

import aiosqlite

from bot.config import DB_PATH

_connection: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Return a shared aiosqlite connection, creating it on first call."""
    global _connection
    if _connection is None:
        _connection = await aiosqlite.connect(str(DB_PATH))
        _connection.row_factory = aiosqlite.Row
        await _connection.execute("PRAGMA journal_mode=WAL")
        await _connection.execute("PRAGMA foreign_keys=ON")
    return _connection


async def close_db() -> None:
    """Close the database connection."""
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None