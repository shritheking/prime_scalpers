import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Bot
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from app.config import settings
from app.database.session import async_session_maker
from app.database.models import Registration, RegistrationStatus, VerificationStatus
from app.services.verification import VerificationService

logger = logging.getLogger(__name__)


class VerificationWorker:
    """Configurable background worker for automated periodic re-checking of pending deposits."""

    def __init__(self, bot: Bot, check_interval_seconds: int = 60):
        self.bot = bot
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start background polling worker."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("VerificationWorker background loop started.")

    async def stop(self) -> None:
        """Gracefully stop worker."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("VerificationWorker background loop stopped.")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self._process_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in VerificationWorker cycle: {e}", exc_info=True)

            # Sleep between evaluation cycles
            await asyncio.sleep(self.check_interval_seconds)

    async def _process_batch(self) -> None:
        if not settings.AUTO_VERIFICATION_ENABLED:
            return

        threshold = datetime.utcnow() - timedelta(minutes=settings.AUTO_RETRY_INTERVAL_MINUTES)

        async with async_session_maker() as session:
            # Query candidate registrations needing re-verification
            stmt = (
                select(Registration)
                .where(
                    and_(
                        Registration.status.notin_([RegistrationStatus.APPROVED, RegistrationStatus.REJECTED, RegistrationStatus.JOINED]),
                        Registration.verification_status.in_([VerificationStatus.DEPOSIT_REQUIRED, VerificationStatus.RETRY_PENDING, VerificationStatus.PENDING]),
                        Registration.retry_count < settings.MAX_AUTO_RETRIES,
                        or_(
                            Registration.last_auto_checked_at == None,
                            Registration.last_auto_checked_at <= threshold
                        )
                    )
                )
                .options(
                    selectinload(Registration.participant),
                    selectinload(Registration.challenge)
                )
                .limit(5)  # Process in small controlled batches
            )
            candidates = list((await session.execute(stmt)).scalars().all())

            if not candidates:
                return

            logger.info(f"VerificationWorker: Found {len(candidates)} pending registrations to re-check.")

            for reg in candidates:
                if not self._running:
                    break

                try:
                    await VerificationService.verify_registration_automated(
                        session=session,
                        registration=reg,
                        bot=self.bot
                    )
                except Exception as e:
                    logger.error(f"Worker failed checking Reg #{reg.id}: {e}")

                # Gentle pacing between queries to respect Telegram flood restrictions
                await asyncio.sleep(4.0)
