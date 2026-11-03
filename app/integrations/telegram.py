import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from aiogram import Bot
from aiogram.types import ChatInviteLink
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


class TelegramChannelManager:
    """Manages secure private channel invitations and membership audits."""

    @staticmethod
    async def create_single_use_invite(
        bot: Bot,
        channel_id: int,
        expiry_hours: int = 24,
        name: str = "Prime Scalpers Invite"
    ) -> Optional[ChatInviteLink]:
        """Generate a strictly single-use invite link (member_limit=1) with expiry."""
        try:
            expire_date = datetime.utcnow() + timedelta(hours=expiry_hours)
            invite: ChatInviteLink = await bot.create_chat_invite_link(
                chat_id=channel_id,
                name=name[:32],
                expire_date=expire_date,
                member_limit=1,
                creates_join_request=False
            )
            logger.info(f"Generated single-use invite link for channel {channel_id}: {invite.invite_link}")
            return invite
        except TelegramAPIError as e:
            logger.error(f"Failed to create single-use invite link: {e}")
            return None

    @staticmethod
    async def revoke_invite(bot: Bot, channel_id: int, invite_link: str) -> bool:
        """Revoke an active invite link immediately."""
        try:
            await bot.revoke_chat_invite_link(chat_id=channel_id, invite_link=invite_link)
            logger.info(f"Revoked invite link: {invite_link}")
            return True
        except TelegramAPIError as e:
            logger.error(f"Failed to revoke invite link {invite_link}: {e}")
            return False

    @staticmethod
    async def check_channel_connection(bot: Bot, channel_id: int) -> Dict[str, Any]:
        """Verify bot admin permissions and connectivity to the private channel."""
        try:
            chat = await bot.get_chat(chat_id=channel_id)
            bot_member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)

            can_invite = getattr(bot_member, "can_invite_users", False) or bot_member.status in ("creator", "administrator")
            can_restrict = getattr(bot_member, "can_restrict_members", False) or bot_member.status in ("creator", "administrator")

            member_count = 0
            try:
                member_count = await bot.get_chat_member_count(chat_id=channel_id)
            except Exception:
                pass

            return {
                "connected": True,
                "title": chat.title or "PRIME SCALPERS",
                "status": bot_member.status,
                "can_invite_users": can_invite,
                "can_restrict_members": can_restrict,
                "member_count": member_count,
                "error": None
            }
        except TelegramAPIError as e:
            logger.warning(f"Channel connection check failed for {channel_id}: {e}")
            return {
                "connected": False,
                "title": None,
                "status": "disconnected",
                "can_invite_users": False,
                "can_restrict_members": False,
                "member_count": 0,
                "error": str(e)
            }

    @staticmethod
    async def get_member_status(bot: Bot, channel_id: int, user_id: int) -> Optional[str]:
        """Check if a specific Telegram user is currently in the channel."""
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            return member.status
        except TelegramAPIError:
            return None

    @staticmethod
    async def remove_member(bot: Bot, channel_id: int, user_id: int) -> bool:
        """Kick (ban and unban) an unauthorized user from the channel."""
        try:
            await bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
            await bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
            logger.info(f"Removed unauthorized user {user_id} from channel {channel_id}")
            return True
        except TelegramAPIError as e:
            logger.error(f"Failed to remove member {user_id} from {channel_id}: {e}")
            return False
