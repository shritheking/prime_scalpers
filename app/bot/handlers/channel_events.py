import logging
from aiogram import Router
from aiogram.types import ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.services.invitation import InvitationService

logger = logging.getLogger(__name__)
router = Router(name="channel_events_router")


@router.chat_member()
async def handle_channel_member_updated(event: ChatMemberUpdated, session: AsyncSession) -> None:
    """Audit joining and leaving members in the private channel."""
    # Only monitor our configured target channel
    if event.chat.id != settings.TELEGRAM_CHANNEL_ID:
        return

    new_user = event.new_chat_member.user
    if new_user.is_bot:
        return

    new_status = event.new_chat_member.status
    logger.info(f"Channel {event.chat.id} member update: {new_user.full_name} ({new_user.id}) -> {new_status}")

    await InvitationService.process_chat_member_update(
        session=session,
        channel_id=event.chat.id,
        user_id=new_user.id,
        user_full_name=new_user.full_name,
        username=new_user.username,
        new_status=new_status,
        bot=event.bot
    )
