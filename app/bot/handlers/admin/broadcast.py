from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.filters.admin import IsAdminFilter
from app.bot.fsm import AdminBroadcastStates
from app.services.broadcast import BroadcastService

router = Router(name="admin_broadcast_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data == "admin_broadcast_start")
async def handle_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Prompt administrator for broadcast message."""
    await state.set_state(AdminBroadcastStates.waiting_for_text)
    text = (
        "📢 <b>BROADCAST TO APPROVED PARTICIPANTS</b>\n\n"
        "Send the announcement text you wish to broadcast to all approved and joined participants.\n\n"
        "<i>Supports HTML formatting (<b>bold</b>, <i>italic</i>, <code>code</code>).</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_dash_view")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_for_text)
async def handle_broadcast_text(message: Message, state: FSMContext) -> None:
    """Preview broadcast and request confirmation."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Message cannot be empty. Please enter text:")
        return

    await state.update_data(broadcast_text=text)
    await state.set_state(AdminBroadcastStates.confirming_broadcast)

    preview_text = (
        "⚠️ <b>CONFIRM BROADCAST TRANSMISSION</b>\n\n"
        "<b>Preview:</b>\n"
        "─────────────────────────────\n"
        f"{text}\n"
        "─────────────────────────────\n"
        "This announcement will be delivered privately to all approved challenge participants."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 SEND BROADCAST NOW", callback_data="admin_broadcast_confirm")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_dash_view")]
        ]
    )
    await message.answer(preview_text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(AdminBroadcastStates.confirming_broadcast, F.data == "admin_broadcast_confirm")
async def handle_broadcast_execute(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Execute broadcast transmission."""
    data = await state.get_data()
    msg_text = data.get("broadcast_text")
    await state.clear()

    await callback.message.edit_text("⏳ <i>Broadcasting in progress...</i>", parse_mode="HTML")

    total, success, failed = await BroadcastService.send_broadcast(
        session=session,
        admin_telegram_id=callback.from_user.id,
        message_text=msg_text,
        target_challenge_id=None,
        bot=callback.bot
    )

    result_text = (
        "✅ <b>BROADCAST COMPLETED</b>\n\n"
        f"<b>Target Recipients:</b> {total}\n"
        f"<b>Successfully Delivered:</b> {success}\n"
        f"<b>Failed:</b> {failed}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_dash_view")]])
    await callback.message.edit_text(result_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("Broadcast finished.")
