from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.bot.filters.admin import IsAdminFilter
from app.bot.keyboards.admin import get_channel_management_keyboard
from app.integrations.telegram import TelegramChannelManager

router = Router(name="admin_channel_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data == "admin_channel_mgmt")
async def handle_channel_mgmt(callback: CallbackQuery) -> None:
    """Channel management overview screen."""
    text = (
        "📡 <b>PRIVATE CHANNEL MANAGEMENT</b>\n\n"
        f"<b>Target Channel:</b> PRIME SCALPERS\n"
        f"<b>Channel ID:</b> <code>{settings.TELEGRAM_CHANNEL_ID}</code>\n\n"
        "Operations:\n"
        "• Verify Bot Administrative Permissions\n"
        "• Single-use invite link monitoring\n"
        "• Automatic removal of unauthorized entrants"
    )
    await callback.message.edit_text(text, reply_markup=get_channel_management_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_channel_test")
async def handle_channel_test(callback: CallbackQuery) -> None:
    """Test channel connection and permissions."""
    res = await TelegramChannelManager.check_channel_connection(
        bot=callback.bot,
        channel_id=settings.TELEGRAM_CHANNEL_ID
    )

    if res["connected"]:
        text = (
            "✅ <b>CHANNEL CONNECTION SUCCESSFUL</b>\n\n"
            f"<b>Channel Title:</b> {res['title']}\n"
            f"<b>Channel ID:</b> <code>{settings.TELEGRAM_CHANNEL_ID}</code>\n"
            f"<b>Bot Status:</b> {res['status']}\n"
            f"<b>Can Create Invites:</b> {'✅ Yes' if res['can_invite_users'] else '❌ No (Grant invite permissions)'}\n"
            f"<b>Can Restrict/Kick:</b> {'✅ Yes' if res['can_restrict_members'] else '❌ No (Grant kick permissions)'}\n"
            f"<b>Total Members:</b> {res['member_count']}\n\n"
            "<i>Bot is ready to issue single-use invites and enforce membership security.</i>"
        )
    else:
        text = (
            "❌ <b>CHANNEL CONNECTION FAILED</b>\n\n"
            f"<b>Channel ID:</b> <code>{settings.TELEGRAM_CHANNEL_ID}</code>\n"
            f"<b>Error:</b> <code>{res['error']}</code>\n\n"
            "⚠️ <b>Setup Checklist:</b>\n"
            "1. Add @PrimeScalpersBot to your private channel as an Administrator.\n"
            "2. Ensure 'Add Subscribers' and 'Ban Users' admin rights are enabled."
        )

    await callback.message.edit_text(text, reply_markup=get_channel_management_keyboard(), parse_mode="HTML")
    await callback.answer()
