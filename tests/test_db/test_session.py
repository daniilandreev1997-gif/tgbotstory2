"""Tests for database session factory."""

import pytest


@pytest.mark.asyncio
async def test_db_session_factory_creates_async_session(test_db_engine):
    from bot.db.session import create_session_factory
    from sqlalchemy import text

    session_factory = create_session_factory(test_db_engine)

    async with session_factory() as session:
        result = await session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1

    assert session.is_active is True
