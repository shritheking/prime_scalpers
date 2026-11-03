import asyncio
import logging
from typing import Optional, Tuple
from aiogram import Bot
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import (
    Registration, RegistrationStatus, Participant, Announcement, AuditLog
)

logger = logging.getLogger(__name__)


class BroadcastService:
    """Manages secure broadcast announcements to approved challenge participants."""

    @staticmethod
    async def send_broadcast(
        session: AsyncSession,
        admin_telegram_id: int,
        message_text: str,
        target_challenge_id: Optional[int],
        bot: Bot
    ) -> Tuple[int, int, int]:
        """Broadcast message to participants with approved or joined status."""
        conditions = [
            Registration.status.in_([RegistrationStatus.APPROVED, RegistrationStatus.INVITED, RegistrationStatus.JOINED])
        ]
        if target_challenge_id:
            conditions.append(Registration.challenge_id == target_challenge_id)

        stmt = (
            select(Participant.telegram_id)
            .join(Registration, Registration.participant_id == Participant.id)
            .where(and_(*conditions))
            .distinct()
        )
        result = await session.execute(stmt)
        recipient_ids = list(result.scalars().all())

        total = len(recipient_ids)
        success = 0
        failed = 0

        broadcast_msg = (
            f"📢 <b>PRIME SCALPERS ANNOUNCEMENT</b>\n\n"
            f"{message_text}\n\n"
            f"─────────────────────\n"
            f"<i>Prime Scalpers Official Operations</i>"
        )

        for uid in recipient_ids:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=broadcast_msg,
                    parse_mode="HTML"
                )
                success += 1
                await asyncio.sleep(0.05)  # Telegram broadcast throttling
            except Exception as e:
                failed += 1
                logger.warning(f"Failed to deliver broadcast to {uid}: {e}")

        # Record announcement
        ann = Announcement(
            admin_telegram_id=admin_telegram_id,
            message_text=message_text,
            target_challenge_id=target_challenge_id,
            total_targets=total,
            success_count=success,
            fail_count=failed
        )
        session.add(ann)

        audit = AuditLog(
            admin_telegram_id=admin_telegram_id,
            action="BROADCAST_MESSAGE",
            target_type="Challenge" if target_challenge_id else "All",
            target_id=str(target_challenge_id or 0),
            details=f"Sent to {success}/{total} participants. Failed: {failed}"
        )
        session.add(audit)
        await session.commit()

        return total, success, failed
