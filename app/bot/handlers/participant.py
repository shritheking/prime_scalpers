import re
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.bot.fsm import RegistrationStates
from app.bot.keyboards.participant import (
    get_start_keyboard,
    get_challenge_selection_keyboard,
    get_account_type_keyboard,
    get_affiliate_notice_keyboard,
    get_confirmation_keyboard,
    get_status_action_keyboard
)
from app.services.challenge import ChallengeService
from app.services.registration import RegistrationService
from app.database.models import RegistrationStatus, VerificationStatus

router = Router(name="participant_router")


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Entry point for participants."""
    await state.clear()

    # Track or update user record
    user = message.from_user
    if user:
        await RegistrationService.get_or_create_participant(
            session=session,
            telegram_id=user.id,
            username=user.username,
            full_name=user.full_name or "Participant"
        )

    welcome_text = (
        "<b>Welcome to Prime Scalpers Challenge!</b>\n\n"
        "Register for the trading challenge, verify your eligibility, "
        "track your registration status and receive exclusive access to the private challenge community.\n\n"
        "<i>Your journey starts here.</i>"
    )
    await message.answer(welcome_text, reply_markup=get_start_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "cancel_to_start")
async def handle_cancel_to_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Reset wizard and return to start menu."""
    await state.clear()
    welcome_text = (
        "<b>Welcome to Prime Scalpers Challenge!</b>\n\n"
        "Register for the trading challenge, verify your eligibility, "
        "track your registration status and receive exclusive access to the private challenge community.\n\n"
        "<i>Your journey starts here.</i>"
    )
    await callback.message.edit_text(welcome_text, reply_markup=get_start_keyboard(), parse_mode="HTML")
    await callback.answer("Registration cancelled.")


@router.callback_query(F.data == "start_register")
async def handle_start_register(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Show open challenges with slot availability."""
    challenges = await ChallengeService.list_open_challenges(session)
    if not challenges:
        await callback.message.edit_text(
            "⚠️ <b>Registrations Currently Closed</b>\n\n"
            "There are currently no active challenge cohorts open. Please check back soon or contact support.",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    text = (
        "🎯 <b>SELECT YOUR CHALLENGE TIER</b>\n\n"
        "Choose an active challenge tier below to view minimum deposit requirements and available slots:\n"
    )
    await state.set_state(RegistrationStates.selecting_challenge)
    await callback.message.edit_text(
        text,
        reply_markup=get_challenge_selection_keyboard(challenges),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(RegistrationStates.selecting_challenge, F.data.startswith("select_challenge:"))
async def handle_select_challenge(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Record selected challenge and proceed to Quotex account selection."""
    challenge_id = int(callback.data.split(":")[1])
    challenge = await ChallengeService.get_challenge_by_id(session, challenge_id)

    if not challenge:
        await callback.answer("Challenge not found.", show_alert=True)
        return

    if challenge.remaining_slots <= 0:
        await callback.answer(f"Sorry, {challenge.name} slots are currently filled.", show_alert=True)
        return

    # Check if participant already registered for this challenge
    user = callback.from_user
    participant = await RegistrationService.get_or_create_participant(
        session=session,
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name or "Participant"
    )
    existing = await RegistrationService.check_duplicate_registration(session, participant.id, challenge.id)
    if existing:
        await callback.message.edit_text(
            f"⚠️ <b>Duplicate Registration Prevented</b>\n\n"
            f"You have already submitted a registration for <b>{challenge.name}</b>.\n"
            f"<b>Status:</b> {existing.status.value}\n"
            f"<b>Verification:</b> {existing.verification_status.value}\n\n"
            f"Use 'My Registration Status' to review progress.",
            reply_markup=get_status_action_keyboard(),
            parse_mode="HTML"
        )
        await state.clear()
        await callback.answer()
        return

    await state.update_data(challenge_id=challenge.id, challenge_name=challenge.name, min_deposit=challenge.minimum_deposit)
    await state.set_state(RegistrationStates.choosing_account_type)

    text = (
        f"<b>Selected: {challenge.name}</b>\n"
        f"<b>Minimum Deposit:</b> ${challenge.minimum_deposit:.0f} USD\n"
        f"<b>Remaining Slots:</b> {challenge.remaining_slots}\n\n"
        f"──────── Quotex Account Status ────────\n"
        f"Eligibility requires verification through our official Quotex affiliate partner link.\n\n"
        f"Do you need to create a new Quotex account or do you have an existing one?"
    )
    await callback.message.edit_text(text, reply_markup=get_account_type_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(RegistrationStates.choosing_account_type, F.data == "acct_new")
async def handle_account_new(callback: CallbackQuery, state: FSMContext) -> None:
    """Guide user to register via the official affiliate link."""
    await state.update_data(account_type="new")
    await state.set_state(RegistrationStates.viewing_affiliate_notice)

    text = (
        "🔗 <b>CREATE YOUR QUOTEX ACCOUNT</b>\n\n"
        "To qualify for the Prime Scalpers challenge:\n"
        f"1. Click the link below to open our official partner registration portal:\n"
        f"   <code>{settings.QUOTEX_AFFILIATE_LINK}</code>\n"
        f"2. Complete your registration.\n"
        f"3. Locate your <b>Quotex Trader ID</b> (numeric ID in your account profile).\n"
        f"4. Return here and tap <b>'I Have Registered, Enter Trader ID'</b>.\n\n"
        f"⚠️ <i>Important: Registrations not attributed to Affiliate ID {settings.QUOTEX_AFFILIATE_LINK_ID} cannot be verified.</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_affiliate_notice_keyboard(settings.QUOTEX_AFFILIATE_LINK),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(RegistrationStates.choosing_account_type, F.data == "acct_existing")
async def handle_account_existing(callback: CallbackQuery, state: FSMContext) -> None:
    """Prompt existing account user and explain attribution check."""
    await state.update_data(account_type="existing")
    await state.set_state(RegistrationStates.entering_trader_id)

    text = (
        "🔑 <b>EXISTING QUOTEX ACCOUNT VERIFICATION</b>\n\n"
        "Please provide your numeric <b>Quotex Trader ID</b>.\n\n"
        "⚠️ <b>Notice on Affiliate Attribution:</b>\n"
        f"Your account must be registered under Affiliate Link ID <code>{settings.QUOTEX_AFFILIATE_LINK_ID}</code>. "
        "Our compliance team will inspect your account attribution before access can be approved.\n\n"
        "<b>Please reply with your Quotex Trader ID now:</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(RegistrationStates.viewing_affiliate_notice, F.data == "enter_trader_id_now")
async def handle_enter_trader_id_now(callback: CallbackQuery, state: FSMContext) -> None:
    """Prompt new user for trader ID."""
    await state.set_state(RegistrationStates.entering_trader_id)
    text = (
        "✍️ <b>ENTER YOUR QUOTEX TRADER ID</b>\n\n"
        "Please enter your numeric Quotex Trader ID (found in your Quotex profile settings):\n\n"
        "<i>Example: 24198231</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(RegistrationStates.viewing_affiliate_notice, F.data == "back_to_account_type")
async def handle_back_to_account_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Go back to account type selection."""
    data = await state.get_data()
    challenge_name = data.get("challenge_name", "Challenge")
    min_deposit = data.get("min_deposit", 100)

    await state.set_state(RegistrationStates.choosing_account_type)
    text = (
        f"<b>Selected: {challenge_name}</b>\n"
        f"<b>Minimum Deposit:</b> ${min_deposit:.0f} USD\n\n"
        f"Do you need to create a new Quotex account or do you have an existing one?"
    )
    await callback.message.edit_text(text, reply_markup=get_account_type_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(RegistrationStates.entering_trader_id)
async def handle_trader_id_input(message: Message, state: FSMContext) -> None:
    """Validate Quotex Trader ID and present confirmation."""
    trader_id_raw = (message.text or "").strip()

    # Validate: Trader ID should be numeric and reasonable length (4 to 15 digits)
    if not trader_id_raw.isdigit() or len(trader_id_raw) < 4 or len(trader_id_raw) > 15:
        await message.answer(
            "❌ <b>Invalid Trader ID Format</b>\n\n"
            "Quotex Trader IDs consist only of numbers (e.g. <code>24198231</code>).\n"
            "Please check your Quotex profile and reply with your valid numeric ID:",
            parse_mode="HTML"
        )
        return

    await state.update_data(quotex_trader_id=trader_id_raw)
    await state.set_state(RegistrationStates.confirming_submission)

    data = await state.get_data()
    user = message.from_user

    summary_text = (
        "📋 <b>REVIEW REGISTRATION DETAILS</b>\n\n"
        f"<b>Participant:</b> {user.full_name}\n"
        f"<b>Telegram Username:</b> @{user.username or 'none'}\n"
        f"<b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"<b>Selected Challenge:</b> {data.get('challenge_name')}\n"
        f"<b>Minimum Deposit:</b> ${data.get('min_deposit', 100):.0f} USD\n"
        f"<b>Quotex Trader ID:</b> <code>{trader_id_raw}</code>\n"
        f"<b>Account Type:</b> {data.get('account_type', 'new').title()}\n"
        f"<b>Registration Timestamp:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        "⚠️ <i>Please confirm all details are accurate before submitting.</i>"
    )
    await message.answer(summary_text, reply_markup=get_confirmation_keyboard(), parse_mode="HTML")


@router.callback_query(RegistrationStates.confirming_submission, F.data == "submit_reg_confirmed")
async def handle_confirm_submission(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Finalize submission and store in database."""
    data = await state.get_data()
    user = callback.from_user

    challenge_id = data.get("challenge_id")
    quotex_trader_id = data.get("quotex_trader_id")
    account_type = data.get("account_type", "new")

    challenge = await ChallengeService.get_challenge_by_id(session, challenge_id)
    if not challenge:
        await callback.message.edit_text("❌ Challenge not found or has been closed.", reply_markup=get_start_keyboard())
        await state.clear()
        await callback.answer()
        return

    participant = await RegistrationService.get_or_create_participant(
        session=session,
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name or "Participant"
    )

    reg, msg = await RegistrationService.create_registration(
        session=session,
        participant=participant,
        challenge=challenge,
        quotex_trader_id=quotex_trader_id,
        account_type=account_type
    )

    await state.clear()

    if not reg:
        await callback.message.edit_text(f"⚠️ {msg}", reply_markup=get_status_action_keyboard(), parse_mode="HTML")
        await callback.answer()
        return

    # Check if automated verification is enabled
    if settings.AUTO_VERIFICATION_ENABLED:
        await callback.message.edit_text(
            f"✅ <b>REGISTRATION #{reg.id} SUBMITTED</b>\n\n"
            f"<b>Trader ID:</b> <code>{quotex_trader_id}</code>\n"
            f"<b>Challenge:</b> {challenge.name}\n\n"
            "⏳ <i>Connecting to Quotex verification engine... Please wait a moment.</i>",
            parse_mode="HTML"
        )
        await callback.answer("Querying Quotex...")

        # Execute automated check
        from app.services.verification import VerificationService
        v_result = await VerificationService.verify_registration_automated(
            session=session,
            registration=reg,
            bot=callback.bot
        )

        # Alert administrators
        for admin_id in settings.admin_ids:
            try:
                await callback.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"📥 <b>NEW REGISTRATION RECEIVED</b>\n\n"
                        f"<b>Reg ID:</b> #{reg.id}\n"
                        f"<b>Participant:</b> {participant.full_name} (@{participant.username or 'none'})\n"
                        f"<b>Telegram ID:</b> <code>{participant.telegram_id}</code>\n"
                        f"<b>Challenge:</b> {challenge.name}\n"
                        f"<b>Trader ID:</b> <code>{quotex_trader_id}</code>\n"
                        f"<b>Auto-Verification:</b> <b>{v_result.status.value}</b>\n"
                        f"<b>Deposit:</b> ${v_result.deposit_amount or 0:.2f} / ${challenge.minimum_deposit:.0f}\n\n"
                        f"Open <code>/admin</code> to inspect."
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass
    else:
        success_text = (
            "✅ <b>REGISTRATION SUBMITTED SUCCESSFULLY!</b>\n\n"
            f"<b>Registration ID:</b> #{reg.id}\n"
            f"<b>Challenge:</b> {challenge.name}\n"
            f"<b>Quotex Trader ID:</b> <code>{quotex_trader_id}</code>\n"
            f"<b>Verification Status:</b> ⏳ PENDING REVIEW\n\n"
            "<b>What happens next?</b>\n"
            "1. Our compliance desk inspects your Quotex Trader ID for affiliate attribution.\n"
            f"2. Ensure you have funded at least <b>${challenge.minimum_deposit:.0f}</b> in your Quotex account.\n"
            "3. Once verified, your challenge slot will be reserved and your personal single-use private channel invitation link will be sent here automatically.\n\n"
            "Use 'My Registration Status' to check verification progress at any time."
        )
        await callback.message.edit_text(success_text, reply_markup=get_status_action_keyboard(), parse_mode="HTML")
        await callback.answer("Registration recorded.")

        # Alert administrators of new registration
        for admin_id in settings.admin_ids:
            try:
                await callback.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"📥 <b>NEW REGISTRATION RECEIVED</b>\n\n"
                        f"<b>Reg ID:</b> #{reg.id}\n"
                        f"<b>Participant:</b> {participant.full_name} (@{participant.username or 'none'})\n"
                        f"<b>Telegram ID:</b> <code>{participant.telegram_id}</code>\n"
                        f"<b>Challenge:</b> {challenge.name}\n"
                        f"<b>Trader ID:</b> <code>{quotex_trader_id}</code>\n"
                        f"<b>Account Type:</b> {account_type.title()}\n\n"
                        f"Open <code>/admin</code> to inspect and verify."
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass


@router.callback_query(F.data == "my_status")
async def handle_my_status(callback: CallbackQuery, session: AsyncSession) -> None:
    """View participant registration status and invitation links."""
    user = callback.from_user
    regs = await RegistrationService.get_participant_registrations(session, user.id)

    if not regs:
        await callback.message.edit_text(
            "ℹ️ <b>No Active Registrations Found</b>\n\n"
            "You have not registered for any Prime Scalpers challenges yet. "
            "Tap below to begin your enrollment:",
            reply_markup=get_start_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    lines = ["📋 <b>YOUR PRIME SCALPERS REGISTRATIONS</b>", "───────────────────────────"]

    for r in regs:
        status_badge = (
            "🟢 APPROVED" if r.status == RegistrationStatus.APPROVED
            else "🚀 INVITED" if r.status == RegistrationStatus.INVITED
            else "⭐️ ACTIVE MEMBER" if r.status == RegistrationStatus.JOINED
            else "🔴 REJECTED" if r.status == RegistrationStatus.REJECTED
            else "⏳ PENDING"
        )

        v_badge = (
            "✅ Verified" if r.verification_status == VerificationStatus.VERIFIED
            else "🔍 Under Manual Review" if r.verification_status == VerificationStatus.MANUAL_REVIEW
            else "⚠️ Deposit Required" if r.verification_status == VerificationStatus.DEPOSIT_REQUIRED
            else "❌ Wrong Affiliate" if r.verification_status == VerificationStatus.WRONG_AFFILIATE
            else "⏳ Pending"
        )

        lines.append(
            f"<b>Challenge:</b> {r.challenge.name}\n"
            f"<b>Registration ID:</b> #{r.id}\n"
            f"<b>Trader ID:</b> <code>{r.quotex_trader_id}</code>\n"
            f"<b>Status:</b> {status_badge}\n"
            f"<b>Verification:</b> {v_badge}\n"
            f"<b>Date:</b> {r.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
        )

        if r.admin_notes:
            lines.append(f"<b>Notice:</b> <i>{r.admin_notes}</i>")

        lines.append("───────────────────────────")

    await callback.message.edit_text("\n".join(lines), reply_markup=get_status_action_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("recheck_deposit:"))
async def handle_recheck_deposit(callback: CallbackQuery, session: AsyncSession) -> None:
    """Manual re-check requested by participant who just funded their Quotex balance."""
    reg_id = int(callback.data.split(":")[1])
    reg = await RegistrationService.get_registration_by_id(session, reg_id)

    if not reg:
        await callback.answer("Registration not found.", show_alert=True)
        return

    if reg.status == RegistrationStatus.APPROVED:
        await callback.answer("You are already approved and invited! Check channel access.", show_alert=True)
        return

    await callback.answer("Re-checking deposit with Quotex Partner Bot...")

    from app.services.verification import VerificationService
    res = await VerificationService.verify_registration_automated(
        session=session,
        registration=reg,
        bot=callback.bot
    )

    if res.status == VerificationStatus.VERIFIED:
        await callback.message.edit_text(
            f"🎉 <b>DEPOSIT CONFIRMED & VERIFIED!</b>\n\n"
            f"<b>Trader ID:</b> <code>{reg.quotex_trader_id}</code>\n"
            f"<b>Verified Deposit:</b> ${res.deposit_amount or 0:.2f} USD\n\n"
            "Your channel invitation link has been generated and sent above!",
            reply_markup=get_status_action_keyboard(),
            parse_mode="HTML"
        )
    elif res.status == VerificationStatus.DEPOSIT_REQUIRED:
        await callback.answer(
            f"Deposit is ${res.deposit_amount or 0:.2f}. Minimum required is ${reg.challenge.minimum_deposit:.0f}.",
            show_alert=True
        )
    else:
        await callback.answer(f"Status: {res.status.value}. {res.message}", show_alert=True)


@router.callback_query(F.data == "contact_support")
async def handle_contact_support(callback: CallbackQuery) -> None:
    """Display official support contact information."""
    support_text = (
        "💬 <b>PRIME SCALPERS SUPPORT & REVIEW DESK</b>\n\n"
        "Need assistance with your challenge application, affiliate verification, or deposit confirmation?\n\n"
        "• <b>Official Review Desk:</b> Direct Admin Review\n"
        f"• <b>Affiliate ID:</b> <code>{settings.QUOTEX_AFFILIATE_LINK_ID}</code>\n"
        f"• <b>Affiliate Link:</b> {settings.QUOTEX_AFFILIATE_LINK}\n\n"
        "Our compliance team reviews registrations within business hours. Make sure your Quotex account has met the minimum deposit."
    )
    await callback.message.edit_text(support_text, reply_markup=get_start_keyboard(), parse_mode="HTML")
    await callback.answer()
