import asyncio
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database.session import init_db
from app.bot.bot_instance import create_bot_and_dispatcher, setup_bot_commands

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("prime_scalpers")

# Background polling and worker references
polling_task: asyncio.Task = None
bot_instance = None
worker_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handling database setup, background worker, and bot lifecycle."""
    global polling_task, bot_instance, worker_instance
    logger.info("Starting Prime Scalpers Challenge System...")

    # 1. Initialize Database & Seed
    await init_db()
    logger.info("Database initialized and verified.")

    # 2. Initialize Telegram Bot
    bot, dp = create_bot_and_dispatcher()
    bot_instance = bot
    await setup_bot_commands(bot)

    # 3. Start Background Automated Verification Worker
    from app.services.worker import VerificationWorker
    worker_instance = VerificationWorker(bot=bot, check_interval_seconds=60)
    worker_instance.start()
    logger.info("Background verification worker active.")

    # 4. Start Telegram Long-Polling in background task with resilient retry loop
    async def start_polling():
        retry_delay = 3
        while True:
            try:
                logger.info("Connecting to Telegram Bot API...")
                # Drop pending updates to avoid processing stale backlog
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("Connected! Starting Telegram Bot Polling...")
                await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
                break
            except asyncio.CancelledError:
                logger.info("Polling task cancelled.")
                break
            except Exception as e:
                logger.warning(
                    f"Temporary network or DNS error connecting to Telegram Bot API ({e}). "
                    f"Retrying in {retry_delay}s..."
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(30, retry_delay * 1.5)

    polling_task = asyncio.create_task(start_polling())
    logger.info("Prime Scalpers backend is active and listening.")

    yield

    # Shutdown sequence
    logger.info("Initiating graceful shutdown...")
    if worker_instance:
        await worker_instance.stop()

    if polling_task and not polling_task.done():
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass

    if bot_instance:
        await bot_instance.session.close()
    logger.info("Shutdown complete.")


# FastAPI Application (for health checks and Render hosting)
app = FastAPI(
    title="Prime Scalpers Challenge Bot API",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint for Render / Docker monitoring."""
    return {
        "status": "healthy",
        "service": "Prime Scalpers Telegram Challenge System",
        "bot_active": polling_task is not None and not polling_task.done()
    }


@app.get("/")
async def root():
    return {
        "name": "Prime Scalpers Bot",
        "channel_id": settings.TELEGRAM_CHANNEL_ID,
        "docs": "https://t.me/PrimeScalpersBot"
    }


def main():
    """CLI launcher for local development or Docker container."""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()
