"""Entry point: bot + scheduler startup.

Initialization order: config -> DB -> bot -> dispatcher -> scheduler -> start polling.
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import load_settings
from bot.db.session import create_engine, create_session_factory, init_db, set_session_factory
from bot.handlers import (
    add_target_router,
    auth_router,
    available_router,
    list_targets_router,
    menu_router,
    remove_target_router,
)
from bot.middleware import StructLogMiddleware
from bot.scheduler import SchedulerService

logger = logging.getLogger(__name__)


def setup_logging(settings) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


async def main() -> None:
    """Main entry point."""
    settings = load_settings()
    setup_logging(settings)

    logger.info("Starting tgbotstory2...")

    # Initialize database
    engine = create_engine(settings.db_path)
    await init_db(engine)
    session_factory = create_session_factory(engine)
    set_session_factory(session_factory)

    # Initialize bot and dispatcher
    bot = Bot(token=settings.bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middlewares
    dp.message.middleware(StructLogMiddleware())
    dp.callback_query.middleware(StructLogMiddleware())

    # Register routers
    dp.include_router(menu_router)
    dp.include_router(add_target_router)
    dp.include_router(remove_target_router)
    dp.include_router(list_targets_router)
    dp.include_router(auth_router)
    dp.include_router(available_router)

    # Initialize scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler_service = SchedulerService(
        scheduler=scheduler,
        session_factory=session_factory,
        bot=bot,
        chat_id=settings.chat_id,
        settings=settings,
    )

    try:
        scheduler_service.start()
        logger.info("Scheduler started with 8 jobs + cleanup")

        # Start polling
        logger.info("Bot polling started")
        await dp.start_polling(bot, handle_signals=False)

    finally:
        logger.info("Shutting down...")
        scheduler_service.stop()
        await bot.session.close()
        await engine.dispose()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
