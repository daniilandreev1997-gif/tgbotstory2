"""Structlog middleware for aiogram.

Logs all incoming updates with structured logging.
"""

import time

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update


class StructLogMiddleware(BaseMiddleware):
    """Middleware that logs all incoming updates via structlog."""

    async def __call__(self, handler, event, data: dict):
        try:
            import structlog
            logger = structlog.get_logger()
        except ImportError:
            return await handler(event, data)

        start_time = time.monotonic()

        if isinstance(event, Message):
            logger.info(
                "message_received",
                user_id=event.from_user.id if event.from_user else None,
                chat_id=event.chat.id,
                text=event.text[:100] if event.text else None,
            )
        elif isinstance(event, CallbackQuery):
            logger.info(
                "callback_received",
                user_id=event.from_user.id,
                data=event.data,
            )

        try:
            result = await handler(event, data)
            elapsed = time.monotonic() - start_time
            logger.info("update_processed", elapsed_ms=round(elapsed * 1000, 2))
            return result
        except Exception as e:
            logger.error("update_failed", error=str(e), error_type=type(e).__name__)
            raise
