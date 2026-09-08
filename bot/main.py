"""Entry point — initialises the Telegram bot, DB, and structlog."""

from __future__ import annotations

import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from telegram.request import HTTPXRequest

from bot.config import load_tg_token
from bot.db import init_db
from bot.db.session import close_db
from bot.handlers import build_monitoring_conv_handler, button_handler, start_command
from bot.scheduler import init_scheduler, restore_jobs, shutdown_scheduler

logger = structlog.get_logger(__name__)


def _configure_logging() -> None:
    """Set up structlog with console + file logging."""
    import logging
    import os

    from bot.config import LOG_DIR

    os.makedirs(LOG_DIR, exist_ok=True)

    file_handler = logging.FileHandler(
        os.path.join(LOG_DIR, "bot.log"), encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.DEBUG)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def _post_init(app: Application) -> None:
    """Initialise database and scheduler after the app is built."""
    await init_db()
    init_scheduler(app.bot)
    await restore_jobs()
    logger.info("post_init_complete")


async def _post_shutdown(app: Application) -> None:
    """Cleanup handlers after the bot stops."""
    await shutdown_scheduler()
    await close_db()
    logger.info("bot_shutdown_complete")


def main() -> None:
    """Start the Telegram bot."""
    _configure_logging()

    tg_token = load_tg_token()
    logger.info("starting_bot")

    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
    )

    app = (
        Application.builder()
        .token(tg_token)
        .request(request)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors and notify user."""
        logger.error("bot_error", error=str(context.error), update=str(update))
        if update and isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла ошибка. Попробуйте /start",
                )
            except Exception:
                pass

    app.add_error_handler(error_handler)

    # Register handlers (ConversationHandler FIRST so add_* callbacks are captured)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(build_monitoring_conv_handler())
    app.add_handler(CallbackQueryHandler(
        button_handler,
        pattern="^(monitoring|main_menu|show_now|platform_|remove_|rm_)",
    ))

    logger.info("bot_polling_start")
    app.run_polling()


if __name__ == "__main__":
    main()