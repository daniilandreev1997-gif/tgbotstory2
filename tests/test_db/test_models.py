"""Tests for SQLAlchemy ORM models."""

import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_target_model_creation():
    from bot.db.models import Target

    target = Target(platform="vk", target_type="user", target_username="test_user", target_id="12345", content_type="stories", is_active=True, added_by=111222333, error_count=0)

    assert target.platform == "vk"
    assert target.target_type == "user"
    assert target.target_username == "test_user"
    assert target.target_id == "12345"
    assert target.content_type == "stories"
    assert target.is_active is True
    assert target.added_by == 111222333
    assert target.error_count == 0
    assert target.last_error is None
    assert target.last_poll_pk is None
    assert target.last_polled_at is None


@pytest.mark.asyncio
async def test_target_unique_constraint():
    from bot.db.models import Target, Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        target1 = Target(platform="vk", target_type="user", target_username="duplicate_user", target_id="12345", content_type="stories")
        session.add(target1)
        session.commit()

        target2 = Target(platform="vk", target_type="user", target_username="duplicate_user_2", target_id="12345", content_type="stories")
        session.add(target2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    engine.dispose()


@pytest.mark.asyncio
async def test_content_hash_creation():
    from bot.db.models import ContentHash

    content_hash = ContentHash(target_id=1, platform="vk", content_pk="story_456789", content_type="story", content_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2", media_urls={"urls": ["https://example.com/photo.jpg"]}, content_meta={"caption": "test"}, telegram_msg_ids=[1, 2, 3])

    assert content_hash.platform == "vk"
    assert content_hash.content_pk == "story_456789"
    assert content_hash.content_type == "story"
    assert len(content_hash.content_hash) == 64
    assert content_hash.media_urls == {"urls": ["https://example.com/photo.jpg"]}
    assert content_hash.telegram_msg_ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_content_hash_unique_constraint_prevents_duplicate():
    from bot.db.models import ContentHash, Base, Target
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        target = Target(platform="vk", target_type="user", target_username="test_user", target_id="12345", content_type="stories")
        session.add(target)
        session.commit()
        session.refresh(target)

        ch1 = ContentHash(target_id=target.id, platform="vk", content_pk="story_456789", content_type="story", content_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")
        session.add(ch1)
        session.commit()

        ch2 = ContentHash(target_id=target.id, platform="vk", content_pk="story_456789", content_type="story", content_hash="b1b2c3d4e5f6b1b2c3d4e5f6b1b2c3d4e5f6b1b2c3d4e5f6b1b2c3d4e5f6b1b2")
        session.add(ch2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    engine.dispose()
