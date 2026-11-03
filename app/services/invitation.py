import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database.models import (
    Registration, RegistrationStatus, InviteLink, ChannelMember,
    AuditLog, Participant
)
from app.integrations.telegram import TelegramChannelManager

logger = logging.getLogger(__name__)


class InvitationService:
    """Manages single-use invitation lifecycle, delivery, and channel entry verification."""

    @staticmethod
    async def issue_and_send_invitation(
        session: AsyncSession,
        registration: Registration,
        bot: Bot
    ) -> Tuple[bool, str]:
        """Generate single-use invite link and deliver privately to approved participant."""
        participant = registration.participant
        challenge = registration.challenge

        expiry_hours = challenge.invite_expiry_hours or settings.DEFAULT_INVITE_EXPIRY_HOURS
        invite = await TelegramChannelManager.create_single_use_invite(
            bot=bot,
            channel_id=settings.TELEGRAM_CHANNEL_ID,
            expiry_hours=expiry_hours,
            name=f"PS-{participant.telegram_id}-{registration.id}"
        )

        if not invite:
            return False, "Could not generate single-use invite link from Telegram API."

        # Save to database
        invite_record = InviteLink(
            registration_id=registration.id,
            participant_telegram_id=participant.telegram_id,
            invite_link=invite.invite_link,
            member_limit=1,
            is_revoked=False,
            is_used=False,
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours)
        )
        session.add(invite_record)
        registration.status = RegistrationStatus.INVITED
        await session.commit()

        # Send private invitation to approved user
        msg = (
            f"🎉 <b>CONGRATULATIONS! YOUR APPLICATION IS APPROVED</b>\n\n"
            f"<b>Challenge:</b> {challenge.name}\n"
            f"<b>Trader ID:</b> <code>{registration.quotex_trader_id}</code>\n"
            f"<b>Status:</b> Approved & Slot Allocated\n\n"
            f"Your personal single-use private channel invitation link has been generated.\n\n"
            f"⚠️ <b>Important Security Rules:</b>\n"
            f"• This link is strictly single-use (1 member limit).\n"
            f"• It will expire in {expiry_hours} hours.\n"
            f"• Do not share this link. Unauthorized accounts will be automatically kicked.\n\n"
            f"Click below to enter the private community:"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Enter Prime Scalpers Channel", url=invite.invite_link)],
                [InlineKeyboardButton(text="📊 View Registration Status", callback_data="my_status")]
            ]
        )

        try:
            await bot.send_message(
                chat_id=participant.telegram_id,
                text=msg,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return True, f"Invitation sent to {participant.full_name} ({participant.telegram_id})."
        except Exception as e:
            logger.error(f"Failed to DM participant {participant.telegram_id}: {e}")
            return False, f"Invite created ({invite.invite_link}) but failed to send DM: {e}"

    @staticmethod
    async def process_chat_member_update(
        session: AsyncSession,
        channel_id: int,
        user_id: int,
        user_full_name: str,
        username: Optional[str],
        new_status: str,
        bot: Bot
    ) -> None:
        """Verify joining Telegram user against approved registrations.

        Kicks unauthorized joiners where Telegram permissions allow.
        """
        # Only process joining events
        if new_status not in ("member", "administrator", "creator"):
            # If user left, update record
            stmt = select(ChannelMember).where(
                and_(
                    ChannelMember.channel_id == channel_id,
                    ChannelMember.telegram_id == user_id
                )
            )
            res = await session.execute(stmt)
            cm = res.scalar_one_or_none()
            if cm:
                cm.status = new_status
                await session.commit()
            return

        # Check if this user has an approved or invited registration
        stmt = (
            select(Registration)
            .join(Participant)
            .where(
                and_(
                    Participant.telegram_id == user_id,
                    Registration.status.in_([RegistrationStatus.APPROVED, RegistrationStatus.INVITED])
                )
            )
            .options(selectinload(Registration.invite_links))
        )
        result = await session.execute(stmt)
        reg = result.scalars().first()

        if reg:
            # Authorized participant!
            reg.status = RegistrationStatus.JOINED
            # Mark invite as used
            for link in reg.invite_links:
                if not link.is_revoked:
                    link.is_used = True

            # Record or update ChannelMember
            cm_stmt = select(ChannelMember).where(
                and_(
                    ChannelMember.channel_id == channel_id,
                    ChannelMember.telegram_id == user_id
                )
            )
            cm_res = await session.execute(cm_stmt)
            cm = cm_res.scalar_one_or_none()
            if not cm:
                cm = ChannelMember(
                    channel_id=channel_id,
                    telegram_id=user_id,
                    registration_id=reg.id,
                    status="member",
                    is_authorized=True
                )
                session.add(cm)
            else:
                cm.status = "member"
                cm.is_authorized = True
                cm.registration_id = reg.id

            await session.commit()
            logger.info(f"Authorized member {user_full_name} ({user_id}) joined channel.")

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"👋 <b>Welcome to Prime Scalpers!</b>\n\n"
                        f"Your membership has been verified and your status is officially active. "
                        f"Check pinned messages in the channel for trade schedules and community guidelines."
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

        else:
            # Unauthorized joiner!
            logger.warning(f"UNAUTHORIZED USER DETECTED IN CHANNEL: {user_full_name} ({user_id})")
            kicked = await TelegramChannelManager.remove_member(bot, channel_id, user_id)

            # Record audit
            audit = AuditLog(
                admin_telegram_id=0,
                action="UNAUTHORIZED_JOIN_REMOVED" if kicked else "UNAUTHORIZED_JOIN_DETECTED",
                target_type="User",
                target_id=str(user_id),
                details=f"User {user_full_name} (@{username}) joined without approved registration. Kicked: {kicked}"
            )
            session.add(audit)
            await session.commit()

            # Alert administrators
            for admin_id in settings.admin_ids:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"🚨 <b>SECURITY ALERT: UNAUTHORIZED USER REMOVED</b>\n\n"
                            f"<b>User:</b> {user_full_name} (@{username or 'no_user'})\n"
                            f"<b>Telegram ID:</b> <code>{user_id}</code>\n"
                            f"<b>Action:</b> Kicked from channel: {kicked}\n"
                            f"<b>Reason:</b> No approved challenge registration record."
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
