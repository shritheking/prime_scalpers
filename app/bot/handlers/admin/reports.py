from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.filters.admin import IsAdminFilter
from app.bot.keyboards.admin import get_reports_keyboard
from app.services.reports import ReportsService

router = Router(name="admin_reports_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data == "admin_reports_view")
async def handle_reports_menu(callback: CallbackQuery) -> None:
    """Display reports options."""
    text = (
        "📑 <b>OPERATIONAL REPORTS & EXPORT</b>\n\n"
        "Generate live registration metrics or export the complete participant database to CSV for offline analysis:"
    )
    await callback.message.edit_text(text, reply_markup=get_reports_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_report_summary")
async def handle_report_summary(callback: CallbackQuery, session: AsyncSession) -> None:
    """Display Telegram text breakdown report."""
    summary_text = await ReportsService.generate_markdown_summary(session)
    await callback.message.edit_text(summary_text, reply_markup=get_reports_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_report_csv")
async def handle_report_csv(callback: CallbackQuery, session: AsyncSession) -> None:
    """Generate and send CSV export file directly to admin in chat."""
    await callback.answer("Generating CSV export...")

    csv_data = await ReportsService.export_registrations_csv(session)
    filename = f"prime_scalpers_registrations_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    file = BufferedInputFile(
        file=csv_data.encode("utf-8"),
        filename=filename
    )

    await callback.bot.send_document(
        chat_id=callback.from_user.id,
        document=file,
        caption=f"📥 <b>Prime Scalpers Registrations Export</b>\nGenerated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        parse_mode="HTML"
    )
