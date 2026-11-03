from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.bot.filters.admin import IsAdminFilter
from app.bot.keyboards.admin import get_admin_dashboard_keyboard
from app.services.reports import ReportsService

router = Router(name="admin_dashboard_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.message(Command("admin"))
async def handle_admin_command(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Entry point for authorized administrators."""
    await state.clear()
    metrics = await ReportsService.get_dashboard_metrics(session)

    text = (
        "🛡️ <b>PRIME SCALPERS • ADMINISTRATOR CONTROL PANEL</b>\n"
        "─────────────────────────────\n"
        f"<b>Active Challenges:</b> {metrics['active_challenges_count']}\n"
        f"<b>Total Registrations:</b> {metrics['total_registrations']}\n"
        f"<b>Pending Verifications:</b> {metrics['pending_verifications']}\n"
        f"<b>In Manual Review:</b> {metrics['manual_review']}\n"
        f"<b>Approved Participants:</b> {metrics['approved_participants']}\n"
        f"<b>Awaiting Deposit:</b> {metrics['deposit_required']}\n"
        f"<b>Total Slots:</b> {metrics['allocated_slots']}/{metrics['total_slots']} allocated "
        f"({metrics['available_slots']} available)\n"
        "─────────────────────────────\n"
        "Select an administrative module below to manage the platform:"
    )
    await message.answer(text, reply_markup=get_admin_dashboard_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_dash_view")
async def handle_admin_dash_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Return to main admin dashboard screen."""
    await state.clear()
    metrics = await ReportsService.get_dashboard_metrics(session)

    text = (
        "🛡️ <b>PRIME SCALPERS • ADMINISTRATOR CONTROL PANEL</b>\n"
        "─────────────────────────────\n"
        f"<b>Active Challenges:</b> {metrics['active_challenges_count']}\n"
        f"<b>Total Registrations:</b> {metrics['total_registrations']}\n"
        f"<b>Pending Verifications:</b> {metrics['pending_verifications']}\n"
        f"<b>In Manual Review:</b> {metrics['manual_review']}\n"
        f"<b>Approved Participants:</b> {metrics['approved_participants']}\n"
        f"<b>Awaiting Deposit:</b> {metrics['deposit_required']}\n"
        f"<b>Total Slots:</b> {metrics['allocated_slots']}/{metrics['total_slots']} allocated "
        f"({metrics['available_slots']} available)\n"
        "─────────────────────────────\n"
        "Select an administrative module below to manage the platform:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_dashboard_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_affiliate_settings")
async def handle_admin_affiliate_settings(callback: CallbackQuery) -> None:
    """Display configured affiliate link and partner ID."""
    text = (
        "🔗 <b>AFFILIATE CONFIGURATION SETTINGS</b>\n\n"
        f"<b>Official Affiliate Link:</b>\n<code>{settings.QUOTEX_AFFILIATE_LINK}</code>\n\n"
        f"<b>Affiliate Tracking ID:</b> <code>{settings.QUOTEX_AFFILIATE_LINK_ID}</code>\n"
        f"<b>Global Min Deposit:</b> ${settings.MINIMUM_DEPOSIT:.2f} USD\n"
        f"<b>Verification Engine:</b> {settings.QUOTEX_VERIFICATION_PROVIDER.upper()}\n\n"
        "<i>To modify affiliate links or partner credentials, update your deployment environment variables.</i>"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="admin_dash_view")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_reg_settings")
async def handle_admin_reg_settings(callback: CallbackQuery) -> None:
    """Display registration & security policies."""
    text = (
        "⚙️ <b>REGISTRATION POLICY & SECURITY SETTINGS</b>\n\n"
        "• <b>Duplicate Prevention:</b> Enforced via database constraint on (participant, challenge).\n"
        f"• <b>Invite Link Lifetime:</b> {settings.DEFAULT_INVITE_EXPIRY_HOURS} Hours.\n"
        "• <b>Invite Member Limit:</b> Exactly 1 member.\n"
        "• <b>Channel Membership Audit:</b> Unauthorized joiners automatically removed.\n"
        f"• <b>Target Channel ID:</b> <code>{settings.TELEGRAM_CHANNEL_ID}</code>"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="admin_dash_view")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
