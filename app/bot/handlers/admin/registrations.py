from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.filters.admin import IsAdminFilter
from app.bot.fsm import AdminSearchStates, AdminManualVerifyStates, AdminRejectStates
from app.bot.keyboards.admin import (
    get_registration_pagination_keyboard,
    get_registration_detail_keyboard,
    get_approval_confirmation_keyboard
)
from app.services.registration import RegistrationService
from app.services.verification import VerificationService
from app.services.invitation import InvitationService
from app.database.models import RegistrationStatus, VerificationStatus

router = Router(name="admin_registrations_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data.startswith("admin_reg_page:"))
async def handle_registration_page(callback: CallbackQuery, session: AsyncSession) -> None:
    """Paginated list of registrations."""
    parts = callback.data.split(":")
    page = int(parts[1])
    filter_type = parts[2] if len(parts) > 2 else "all"

    filter_status = None
    filter_v = None
    if filter_type == "pending":
        filter_v = VerificationStatus.PENDING
    elif filter_type == "approved":
        filter_status = RegistrationStatus.APPROVED

    regs, total = await RegistrationService.get_paginated_registrations(
        session=session,
        page=page,
        per_page=5,
        filter_status=filter_status,
        filter_verification=filter_v
    )

    title = (
        "⏳ <b>PENDING VERIFICATIONS</b>" if filter_type == "pending"
        else "✅ <b>APPROVED PARTICIPANTS</b>" if filter_type == "approved"
        else "📋 <b>ALL REGISTRATIONS</b>"
    )

    if not regs:
        text = f"{title}\n\n<i>No registrations found for this filter.</i>"
    else:
        text = f"{title}\nTotal: {total} records | Page {page}\n\nSelect a participant to review details:"

    await callback.message.edit_text(
        text,
        reply_markup=get_registration_pagination_keyboard(regs, page, total, filter_type),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reg_detail:"))
async def handle_registration_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    """Detailed view of a single participant registration."""
    reg_id = int(callback.data.split(":")[1])
    reg = await RegistrationService.get_registration_by_id(session, reg_id)

    if not reg:
        await callback.answer("Registration not found.", show_alert=True)
        return

    p = reg.participant
    c = reg.challenge

    text = (
        f"📄 <b>REGISTRATION #{reg.id} DETAILS</b>\n"
        "─────────────────────────────\n"
        f"<b>Participant:</b> {p.full_name}\n"
        f"<b>Username:</b> @{p.username or 'none'}\n"
        f"<b>Telegram ID:</b> <code>{p.telegram_id}</code>\n"
        f"<b>Challenge:</b> {c.name} (Min: ${c.minimum_deposit:.0f})\n"
        f"<b>Quotex Trader ID:</b> <code>{reg.quotex_trader_id}</code>\n"
        f"<b>Account Type:</b> {reg.account_type.title()}\n"
        f"<b>Registration Status:</b> <b>{reg.status.value}</b>\n"
        f"<b>Verification Status:</b> <b>{reg.verification_status.value}</b>\n"
        f"<b>Slot Reserved:</b> {'Yes' if reg.slot_reserved else 'No'}\n"
        f"<b>Created At:</b> {reg.created_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
    )
    if reg.admin_notes:
        text += f"<b>Admin Notes:</b> <i>{reg.admin_notes}</i>\n"

    # Display active invites if any
    if reg.invite_links:
        active_inv = next((inv for inv in reg.invite_links if not inv.is_revoked), None)
        if active_inv:
            text += f"\n🔗 <b>Active Invite:</b> <code>{active_inv.invite_link}</code>\n"
            text += f"<b>Invite Used:</b> {'Yes' if active_inv.is_used else 'No'}\n"

    text += "─────────────────────────────\nChoose an administrative action:"

    await callback.message.edit_text(text, reply_markup=get_registration_detail_keyboard(reg.id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_verify_auto:"))
async def handle_admin_verify_auto(callback: CallbackQuery, session: AsyncSession) -> None:
    """Manually trigger automated Quotex verification for a specific registration."""
    reg_id = int(callback.data.split(":")[1])
    reg = await RegistrationService.get_registration_by_id(session, reg_id)
    if not reg:
        await callback.answer("Registration not found.")
        return

    await callback.answer("Querying Quotex verification engine...")

    v_result = await VerificationService.verify_registration_automated(
        session=session,
        registration=reg,
        bot=callback.bot
    )

    p = reg.participant
    c = reg.challenge
    raw = v_result.raw_data or {}

    summary = (
        f"🤖 <b>AUTOMATED VERIFICATION COMPLETED</b>\n"
        "─────────────────────────────\n"
        f"<b>Registration:</b> #{reg.id}\n"
        f"<b>Participant:</b> {p.full_name}\n"
        f"<b>Trader ID:</b> <code>{reg.quotex_trader_id}</code>\n"
        f"<b>Challenge:</b> {c.name} (Min: ${c.minimum_deposit:.0f})\n\n"
        f"<b>Status:</b> <b>{v_result.status.value}</b>\n"
        f"<b>Extracted Link ID:</b> <code>{v_result.affiliate_link_id or 'N/A'}</code>\n"
        f"<b>Deposits Sum:</b> ${v_result.deposit_amount or 0:.2f} USD\n"
        f"<b>Balance:</b> ${raw.get('balance', 0):.2f}\n"
        f"<b>Country:</b> {raw.get('country', 'N/A')}\n"
        f"<b>Registration Date:</b> {raw.get('registration_date', 'N/A')}\n\n"
        f"<b>Result Message:</b>\n<i>{v_result.message}</i>\n"
        "─────────────────────────────"
    )

    await callback.message.edit_text(summary, reply_markup=get_registration_detail_keyboard(reg.id), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_verify_hist:"))
async def handle_admin_verify_hist(callback: CallbackQuery, session: AsyncSession) -> None:
    """Display verification audit history for a registration."""
    reg_id = int(callback.data.split(":")[1])
    from sqlalchemy import select
    from app.database.models import VerificationResult

    stmt = select(VerificationResult).where(VerificationResult.registration_id == reg_id).order_by(VerificationResult.created_at.desc())
    results = list((await session.execute(stmt)).scalars().all())

    if not results:
        await callback.answer("No verification logs recorded for this registration.", show_alert=True)
        return

    lines = [f"📜 <b>VERIFICATION HISTORY • REG #{reg_id}</b>", "─────────────────────────────"]
    for r in results:
        verifier = "Automated Provider" if not r.verified_by_admin_id else f"Admin ID {r.verified_by_admin_id}"
        lines.append(
            f"• <b>{r.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</b> by {verifier}\n"
            f"  Affiliate ID: {r.affiliate_link_id or 'None'} | Deposit: ${r.deposit_amount or 0:.2f}\n"
            f"  Matched: {'Yes' if r.is_affiliate_matched else 'No'} | Sufficient: {'Yes' if r.is_deposit_sufficient else 'No'}\n"
            f"  Notes: <i>{r.notes or 'None'}</i>"
        )
    lines.append("─────────────────────────────")

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Registration", callback_data=f"reg_detail:{reg_id}")]])
    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_auto_settings")
async def handle_auto_settings(callback: CallbackQuery) -> None:
    """View and toggle automated verification settings."""
    from app.bot.keyboards.admin import get_auto_verification_settings_keyboard

    provider = settings.QUOTEX_VERIFICATION_PROVIDER.upper()
    status_str = "🟢 ACTIVE" if settings.AUTO_VERIFICATION_ENABLED else "🔴 DISABLED"

    text = (
        "🤖 <b>AUTOMATED VERIFICATION ENGINE SETTINGS</b>\n\n"
        f"<b>Auto-Verification State:</b> {status_str}\n"
        f"<b>Active Provider:</b> {provider}\n"
        f"<b>Expected Link ID:</b> <code>{settings.QUOTEX_AFFILIATE_LINK_ID}</code>\n"
        f"<b>Partner Bot Username:</b> @{settings.QUOTEX_PARTNER_BOT_USERNAME}\n"
        f"<b>Background Retry Interval:</b> Every {settings.AUTO_RETRY_INTERVAL_MINUTES} minutes\n"
        f"<b>Max Auto Retries:</b> {settings.MAX_AUTO_RETRIES} attempts\n\n"
        "<i>When enabled, incoming registrations and deposit re-checks query Quotex automatically without administrator manual intervention.</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_auto_verification_settings_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_toggle_auto_verif")
async def handle_toggle_auto_verif(callback: CallbackQuery) -> None:
    """Toggle automated verification on or off."""
    settings.AUTO_VERIFICATION_ENABLED = not settings.AUTO_VERIFICATION_ENABLED
    await callback.answer(f"Automated verification is now {'ENABLED' if settings.AUTO_VERIFICATION_ENABLED else 'DISABLED'}")
    await handle_auto_settings(callback)


@router.callback_query(F.data == "admin_trigger_batch_check")
async def handle_trigger_batch_check(callback: CallbackQuery, session: AsyncSession) -> None:
    """Trigger manual run of the automated background verification cycle."""
    await callback.answer("Starting batch verification cycle...")
    from app.services.worker import VerificationWorker

    worker = VerificationWorker(bot=callback.bot)
    await worker._process_batch()

    await callback.message.answer("✅ Batch automated verification cycle completed.")


@router.callback_query(F.data.startswith("admin_verify_manual:"))
async def handle_start_manual_verify(callback: CallbackQuery, state: FSMContext) -> None:
    """Start manual verification wizard for an administrator."""
    reg_id = int(callback.data.split(":")[1])
    await state.set_state(AdminManualVerifyStates.waiting_for_affiliate_id)
    await state.update_data(verifying_reg_id=reg_id)

    text = (
        f"🔍 <b>MANUAL QUOTEX VERIFICATION • REG #{reg_id}</b>\n\n"
        "Step 1 of 2: Log into your Quotex Partner Portal and locate the Trader ID.\n\n"
        "<b>Please reply with the observed Affiliate Link ID from Quotex:</b>\n"
        "<i>(Enter the ID, e.g. 2414647, or send 0 if not found / different)</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(AdminManualVerifyStates.waiting_for_affiliate_id)
async def handle_manual_affiliate_id_input(message: Message, state: FSMContext) -> None:
    """Collect observed affiliate ID."""
    affiliate_id = (message.text or "").strip()
    await state.update_data(observed_affiliate_id=affiliate_id)
    await state.set_state(AdminManualVerifyStates.waiting_for_deposit_amount)

    await message.answer(
        "Step 2 of 2: <b>Enter total deposited USD amount for this trader:</b>\n"
        "<i>(Enter numeric amount, e.g. 150, or 0 if no deposit has been made)</i>",
        parse_mode="HTML"
    )


@router.message(AdminManualVerifyStates.waiting_for_deposit_amount)
async def handle_manual_deposit_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Complete manual verification calculation."""
    deposit_raw = (message.text or "").strip().replace("$", "")
    try:
        deposit = float(deposit_raw)
    except ValueError:
        await message.answer("❌ Invalid amount. Please enter a valid number (e.g. 100):")
        return

    data = await state.get_data()
    reg_id = data.get("verifying_reg_id")
    affiliate_id = data.get("observed_affiliate_id")

    success, msg, reg = await VerificationService.record_manual_verification(
        session=session,
        registration_id=reg_id,
        admin_telegram_id=message.from_user.id,
        observed_affiliate_id=affiliate_id,
        observed_deposit=deposit
    )
    await state.clear()

    result_text = (
        f"✅ <b>MANUAL VERIFICATION RECORDED</b>\n\n"
        f"<b>Registration:</b> #{reg.id}\n"
        f"<b>Trader ID:</b> <code>{reg.quotex_trader_id}</code>\n"
        f"<b>Observed Affiliate ID:</b> <code>{affiliate_id}</code>\n"
        f"<b>Observed Deposit:</b> ${deposit:.2f}\n"
        f"<b>Resulting Status:</b> <b>{reg.verification_status.value}</b>\n\n"
        f"<i>{msg}</i>"
    )
    await message.answer(result_text, reply_markup=get_registration_detail_keyboard(reg.id), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_approve_confirm:"))
async def handle_approve_confirm(callback: CallbackQuery) -> None:
    """Prompt 2-step confirmation before approval."""
    reg_id = int(callback.data.split(":")[1])
    text = (
        f"⚠️ <b>CONFIRM APPROVAL • REG #{reg_id}</b>\n\n"
        "Are you sure you want to approve this participant?\n\n"
        "This will:\n"
        "1. Atomically reserve a challenge slot.\n"
        "2. Generate a single-use private channel invitation link.\n"
        "3. Deliver the invite link privately to the participant."
    )
    await callback.message.edit_text(text, reply_markup=get_approval_confirmation_keyboard(reg_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_approve_execute:"))
async def handle_approve_execute(callback: CallbackQuery, session: AsyncSession) -> None:
    """Execute approval, slot allocation, and invite link delivery."""
    reg_id = int(callback.data.split(":")[1])

    success, msg, reg = await VerificationService.approve_and_allocate_slot(
        session=session,
        registration_id=reg_id,
        admin_telegram_id=callback.from_user.id
    )

    if not success:
        await callback.message.edit_text(
            f"❌ <b>Approval Failed</b>\n\n{msg}",
            reply_markup=get_registration_detail_keyboard(reg_id),
            parse_mode="HTML"
        )
        await callback.answer("Approval failed.", show_alert=True)
        return

    # Deliver invitation link
    inv_success, inv_msg = await InvitationService.issue_and_send_invitation(
        session=session,
        registration=reg,
        bot=callback.bot
    )

    result_text = (
        f"✅ <b>PARTICIPANT APPROVED & INVITED</b>\n\n"
        f"<b>Registration:</b> #{reg.id}\n"
        f"<b>Participant:</b> {reg.participant.full_name}\n"
        f"<b>Challenge:</b> {reg.challenge.name}\n"
        f"<b>Slot Allocated:</b> {reg.challenge.allocated_slots}/{reg.challenge.max_slots}\n"
        f"<b>Invitation Delivery:</b> {inv_msg}"
    )
    await callback.message.edit_text(result_text, reply_markup=get_registration_detail_keyboard(reg.id), parse_mode="HTML")
    await callback.answer("Participant approved!")


@router.callback_query(F.data.startswith("admin_mark_deposit:"))
async def handle_mark_deposit(callback: CallbackQuery, session: AsyncSession) -> None:
    """Mark as deposit required and notify user."""
    reg_id = int(callback.data.split(":")[1])
    reg = await RegistrationService.get_registration_by_id(session, reg_id)
    if not reg:
        await callback.answer("Registration not found.")
        return

    reg.verification_status = VerificationStatus.DEPOSIT_REQUIRED
    await session.commit()

    # Notify participant
    try:
        await callback.bot.send_message(
            chat_id=reg.participant.telegram_id,
            text=(
                f"⚠️ <b>PRIME SCALPERS • DEPOSIT REQUIRED</b>\n\n"
                f"Your registration for <b>{reg.challenge.name}</b> has been checked.\n"
                f"Your Quotex Trader ID <code>{reg.quotex_trader_id}</code> is affiliated, but requires a minimum deposit of "
                f"<b>${reg.challenge.minimum_deposit:.0f} USD</b> to qualify for channel access.\n\n"
                f"Please fund your Quotex account and check status via 'My Registration Status'."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"⚠️ Marked #{reg.id} as <b>DEPOSIT_REQUIRED</b>. Participant notified.",
        reply_markup=get_registration_detail_keyboard(reg.id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_reject_start:"))
async def handle_reject_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Prompt for rejection reason."""
    reg_id = int(callback.data.split(":")[1])
    await state.set_state(AdminRejectStates.waiting_for_reason)
    await state.update_data(rejecting_reg_id=reg_id)

    await callback.message.edit_text(
        f"❌ <b>REJECT REGISTRATION #{reg_id}</b>\n\n"
        "Please reply with the rejection reason to send to the participant:\n"
        "<i>(e.g., Quotex account not registered under our partner link)</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminRejectStates.waiting_for_reason)
async def handle_reject_reason(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Finalize rejection with reason."""
    reason = (message.text or "").strip()
    data = await state.get_data()
    reg_id = data.get("rejecting_reg_id")

    success, msg, reg = await VerificationService.reject_registration(
        session=session,
        registration_id=reg_id,
        admin_telegram_id=message.from_user.id,
        reason=reason
    )
    await state.clear()

    # Notify participant
    if reg:
        try:
            await message.bot.send_message(
                chat_id=reg.participant.telegram_id,
                text=(
                    f"❌ <b>PRIME SCALPERS REGISTRATION UPDATE</b>\n\n"
                    f"Your registration for <b>{reg.challenge.name}</b> could not be approved.\n\n"
                    f"<b>Reason:</b> {reason}\n\n"
                    "If you believe this is in error, please contact support or re-register through the official affiliate link."
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    await message.answer(
        f"❌ Registration #{reg_id} has been REJECTED. Participant notified.",
        reply_markup=get_registration_detail_keyboard(reg_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_search_start")
async def handle_admin_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Prompt admin for search query."""
    await state.set_state(AdminSearchStates.waiting_for_query)
    await callback.message.edit_text(
        "🔍 <b>SEARCH PARTICIPANTS</b>\n\n"
        "Reply with any of the following:\n"
        "• Quotex Trader ID (e.g. <code>24198231</code>)\n"
        "• Telegram User ID (e.g. <code>5188160752</code>)\n"
        "• Participant Name or @Username",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminSearchStates.waiting_for_query)
async def handle_admin_search_query(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Execute search and present results."""
    query = (message.text or "").strip()
    await state.clear()

    regs = await RegistrationService.search_registrations(session, query)
    if not regs:
        await message.answer(f"🔍 No registrations matched query: <code>{query}</code>")
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for r in regs:
        p_name = r.participant.full_name if r.participant else "User"
        buttons.append([
            InlineKeyboardButton(
                text=f"#{r.id} • {p_name} • Trader: {r.quotex_trader_id}",
                callback_data=f"reg_detail:{r.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_dash_view")])

    await message.answer(
        f"🔍 Found {len(regs)} registrations for '<code>{query}</code>':",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
