"""Database operations — targets, sent_items, tt_post_index, error_cooldown."""

from __future__ import annotations

import structlog
from bot.db.session import get_db

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """Create all tables if they don't exist."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            target TEXT NOT NULL,
            display_name TEXT NOT NULL,
            added_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(chat_id, platform, target)
        );

        CREATE TABLE IF NOT EXISTS sent_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            target TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_type TEXT NOT NULL,
            sent_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(chat_id, platform, target, item_id)
        );

        CREATE TABLE IF NOT EXISTS tt_post_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            target TEXT NOT NULL,
            total_found INTEGER NOT NULL DEFAULT 0,
            last_sent_index INTEGER NOT NULL DEFAULT -1,
            UNIQUE(chat_id, target)
        );

        CREATE TABLE IF NOT EXISTS error_cooldown (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            target TEXT NOT NULL,
            last_error_at TEXT NOT NULL,
            error_count INTEGER NOT NULL DEFAULT 1,
            UNIQUE(chat_id, platform, target)
        );

        CREATE INDEX IF NOT EXISTS idx_targets_chat ON targets(chat_id);
        CREATE INDEX IF NOT EXISTS idx_sent_items_lookup ON sent_items(chat_id, platform, target, item_id);
    """)
    await db.commit()
    logger.info("database_initialized")


# ---------------------------------------------------------------------------
# Targets CRUD
# ---------------------------------------------------------------------------

async def add_target(
    chat_id: int, platform: str, target: str, display_name: str,
) -> bool:
    """Add a target. Returns True if inserted, False if already exists."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO targets (chat_id, platform, target, display_name) VALUES (?, ?, ?, ?)",
            (chat_id, platform, target, display_name),
        )
        await db.commit()
        logger.info("target_added", chat_id=chat_id, platform=platform, target=target)
        return True
    except Exception:
        return False


async def remove_target(
    chat_id: int, platform: str, target: str,
) -> bool:
    """Remove a target. Returns True if deleted, False if not found."""
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM targets WHERE chat_id = ? AND platform = ? AND target = ?",
        (chat_id, platform, target),
    )
    await db.commit()
    deleted = cursor.rowcount > 0
    if deleted:
        logger.info("target_removed", chat_id=chat_id, platform=platform, target=target)
    return deleted


async def get_targets(
    chat_id: int, platform: str | None = None,
) -> list[dict]:
    """Get all targets for a chat, optionally filtered by platform."""
    db = await get_db()
    if platform:
        cursor = await db.execute(
            "SELECT id, chat_id, platform, target, display_name, added_at "
            "FROM targets WHERE chat_id = ? AND platform = ? ORDER BY id",
            (chat_id, platform),
        )
    else:
        cursor = await db.execute(
            "SELECT id, chat_id, platform, target, display_name, added_at "
            "FROM targets WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def count_targets(chat_id: int) -> int:
    """Count total targets for a chat."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM targets WHERE chat_id = ?", (chat_id,),
    )
    row = await cursor.fetchone()
    return row["cnt"] if row else 0


async def get_all_chat_ids() -> list[int]:
    """Return distinct chat_ids that have at least one target."""
    db = await get_db()
    cursor = await db.execute("SELECT DISTINCT chat_id FROM targets")
    rows = await cursor.fetchall()
    return [r["chat_id"] for r in rows]


# ---------------------------------------------------------------------------
# Sent items (dedup)
# ---------------------------------------------------------------------------

async def is_item_sent(
    chat_id: int, platform: str, target: str, item_id: str, item_type: str,
) -> bool:
    """Check whether an item has already been sent."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT 1 FROM sent_items "
        "WHERE chat_id = ? AND platform = ? AND target = ? AND item_id = ? AND item_type = ?",
        (chat_id, platform, target, item_id, item_type),
    )
    row = await cursor.fetchone()
    return row is not None


async def mark_item_sent(
    chat_id: int, platform: str, target: str, item_id: str, item_type: str,
) -> None:
    """Record that an item has been sent."""
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO sent_items (chat_id, platform, target, item_id, item_type) "
        "VALUES (?, ?, ?, ?, ?)",
        (chat_id, platform, target, item_id, item_type),
    )
    await db.commit()
    logger.debug(
        "item_marked_sent",
        chat_id=chat_id, platform=platform, target=target, item_id=item_id,
    )


# ---------------------------------------------------------------------------
# TT Post Index
# ---------------------------------------------------------------------------

async def get_tt_post_index(
    chat_id: int, target: str,
) -> dict | None:
    """Get TT post index row for a chat/target."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT total_found, last_sent_index FROM tt_post_index "
        "WHERE chat_id = ? AND target = ?",
        (chat_id, target),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_tt_post_index(
    chat_id: int, target: str, total_found: int, last_sent_index: int,
) -> None:
    """Upsert TT post index."""
    db = await get_db()
    await db.execute(
        "INSERT INTO tt_post_index (chat_id, target, total_found, last_sent_index) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id, target) DO UPDATE SET "
        "total_found = excluded.total_found, last_sent_index = excluded.last_sent_index",
        (chat_id, target, total_found, last_sent_index),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Error cooldown
# ---------------------------------------------------------------------------

async def is_in_cooldown(
    chat_id: int, platform: str, target: str, cooldown_minutes: int = 30,
) -> bool:
    """Check if a target is in error cooldown."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT last_error_at FROM error_cooldown "
        "WHERE chat_id = ? AND platform = ? AND target = ?",
        (chat_id, platform, target),
    )
    row = await cursor.fetchone()
    if not row:
        return False

    from datetime import datetime, timedelta, timezone
    last_error = datetime.strptime(row["last_error_at"], "%Y-%m-%d %H:%M:%S")
    last_error = last_error.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last_error < timedelta(minutes=cooldown_minutes)


async def get_error_count(
    chat_id: int, platform: str, target: str,
) -> int:
    """Get current error count for a target."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT error_count FROM error_cooldown "
        "WHERE chat_id = ? AND platform = ? AND target = ?",
        (chat_id, platform, target),
    )
    row = await cursor.fetchone()
    return row["error_count"] if row else 0


async def set_error_cooldown(
    chat_id: int, platform: str, target: str,
) -> None:
    """Record an error and increment cooldown counter."""
    db = await get_db()
    await db.execute(
        "INSERT INTO error_cooldown (chat_id, platform, target, last_error_at, error_count) "
        "VALUES (?, ?, ?, datetime('now'), 1) "
        "ON CONFLICT(chat_id, platform, target) DO UPDATE SET "
        "last_error_at = datetime('now'), error_count = error_count + 1",
        (chat_id, platform, target),
    )
    await db.commit()
    logger.debug(
        "error_cooldown_set", chat_id=chat_id, platform=platform, target=target,
    )


async def clear_error_cooldown(
    chat_id: int, platform: str, target: str,
) -> None:
    """Clear error cooldown on successful poll."""
    db = await get_db()
    await db.execute(
        "DELETE FROM error_cooldown WHERE chat_id = ? AND platform = ? AND target = ?",
        (chat_id, platform, target),
    )
    await db.commit()