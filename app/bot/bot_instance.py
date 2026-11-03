import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from app.config import settings
from app.bot.middlewares.db_session import DbSessionMiddleware
from app.bot.handlers import participant, channel_events
from app.bot.handlers.admin import (
    dashboard as admin_dashboard,
    registrations as admin_registrations,
    challenges as admin_challenges,
    channel as admin_channel,
    broadcast as admin_broadcast,
    reports as admin_reports
)

# Cross-platform Windows/Linux SSL certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

logger = logging.getLogger(__name__)


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """Factory creating bot and configured dispatcher."""
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Attach database middleware to all relevant update types
    db_middleware = DbSessionMiddleware()
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)
    dp.chat_member.middleware(db_middleware)

    # Register admin routers first (to ensure admin commands take precedence)
    dp.include_router(admin_dashboard.router)
    dp.include_router(admin_registrations.router)
    dp.include_router(admin_challenges.router)
    dp.include_router(admin_channel.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_reports.router)

    # Register participant and event routers
    dp.include_router(channel_events.router)
    dp.include_router(participant.router)

    return bot, dp
