from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.filters.admin import IsAdminFilter
from app.bot.fsm import AdminChallengeCreateStates, AdminChallengeEditSlotsStates
from app.bot.keyboards.admin import (
    get_challenges_management_keyboard,
    get_challenge_detail_keyboard
)
from app.services.challenge import ChallengeService
from app.database.models import ChallengeStatus

router = Router(name="admin_challenges_router")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


@router.callback_query(F.data == "admin_challenges_list")
async def handle_challenges_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """Display list of all challenges."""
    challenges = await ChallengeService.list_all_challenges(session)
    text = (
        "🎯 <b>CHALLENGE COHORTS MANAGEMENT</b>\n\n"
        "Select a challenge to toggle registration status, edit slots, or inspect allocations:\n"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_challenges_management_keyboard(challenges),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_slots_manage")
async def handle_slots_manage_shortcut(callback: CallbackQuery, session: AsyncSession) -> None:
    """Direct shortcut to slot management."""
    await handle_challenges_list(callback, session)


@router.callback_query(F.data.startswith("admin_chal_detail:"))
async def handle_challenge_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    """View details of a single challenge."""
    challenge_id = int(callback.data.split(":")[1])
    c = await ChallengeService.get_challenge_by_id(session, challenge_id)
    if not c:
        await callback.answer("Challenge not found.")
        return

    fill_pct = int((c.allocated_slots / c.max_slots) * 100) if c.max_slots > 0 else 0
    text = (
        f"🎯 <b>CHALLENGE: {c.name}</b>\n"
        "─────────────────────────────\n"
        f"<b>Status:</b> {c.status.value}\n"
        f"<b>Minimum Deposit:</b> ${c.minimum_deposit:.2f} USD\n"
        f"<b>Total Slots:</b> {c.max_slots}\n"
        f"<b>Allocated Slots:</b> {c.allocated_slots} ({fill_pct}% filled)\n"
        f"<b>Remaining Slots:</b> {c.remaining_slots}\n"
        f"<b>Affiliate ID:</b> <code>{c.affiliate_link_id}</code>\n"
        f"<b>Invite Expiry:</b> {c.invite_expiry_hours} Hours\n\n"
        f"<b>Description:</b>\n<i>{c.description or 'No description'}</i>"
    )
    is_open = c.status == ChallengeStatus.OPEN
    await callback.message.edit_text(
        text,
        reply_markup=get_challenge_detail_keyboard(c.id, is_open),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_chal_toggle:"))
async def handle_challenge_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    """Open or close challenge registrations."""
    parts = callback.data.split(":")
    challenge_id = int(parts[1])
    action = parts[2]

    new_status = ChallengeStatus.CLOSED if action == "close" else ChallengeStatus.OPEN
    updated = await ChallengeService.toggle_challenge_status(session, challenge_id, new_status)

    if updated:
        await callback.answer(f"Challenge is now {updated.status.value}!")
        await handle_challenge_detail(callback, session)
    else:
        await callback.answer("Update failed.")


@router.callback_query(F.data.startswith("admin_chal_slots:"))
async def handle_challenge_edit_slots_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """Prompt for new max slots value."""
    challenge_id = int(callback.data.split(":")[1])
    c = await ChallengeService.get_challenge_by_id(session, challenge_id)
    if not c:
        await callback.answer("Challenge not found.")
        return

    await state.set_state(AdminChallengeEditSlotsStates.waiting_for_new_slots)
    await state.update_data(editing_challenge_id=c.id)

    text = (
        f"🔢 <b>EDIT SLOTS FOR {c.name}</b>\n\n"
        f"Current Slots: {c.allocated_slots} allocated / {c.max_slots} maximum.\n\n"
        f"⚠️ <i>Note: You cannot reduce maximum slots below {c.allocated_slots} (already allocated).</i>\n\n"
        "<b>Please reply with the new maximum slot capacity:</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(AdminChallengeEditSlotsStates.waiting_for_new_slots)
async def handle_challenge_edit_slots_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Process new slot capacity with validation."""
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ Please enter a valid positive number:")
        return

    new_slots = int(raw)
    data = await state.get_data()
    challenge_id = data.get("editing_challenge_id")

    success, msg = await ChallengeService.update_challenge_slots(session, challenge_id, new_slots)
    await state.clear()

    if success:
        await message.answer(f"✅ {msg}")
    else:
        await message.answer(f"❌ {msg}")


@router.callback_query(F.data == "admin_chal_create")
async def handle_challenge_create_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Start wizard to create new challenge."""
    await state.set_state(AdminChallengeCreateStates.waiting_for_name)
    await callback.message.edit_text(
        "➕ <b>CREATE NEW CHALLENGE COHORT</b>\n\n"
        "Step 1 of 3: Enter the challenge name\n"
        "<i>(Example: $250 Scalping Bootcamp)</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminChallengeCreateStates.waiting_for_name)
async def handle_create_name(message: Message, state: FSMContext) -> None:
    """Record name and prompt min deposit."""
    name = (message.text or "").strip()
    await state.update_data(new_name=name)
    await state.set_state(AdminChallengeCreateStates.waiting_for_min_deposit)
    await message.answer(
        f"Step 2 of 3: Enter minimum USD deposit required for <b>{name}</b>:\n"
        "<i>(Example: 250)</i>",
        parse_mode="HTML"
    )


@router.message(AdminChallengeCreateStates.waiting_for_min_deposit)
async def handle_create_min_deposit(message: Message, state: FSMContext) -> None:
    """Record min deposit and prompt max slots."""
    raw = (message.text or "").strip().replace("$", "")
    try:
        min_dep = float(raw)
    except ValueError:
        await message.answer("❌ Invalid amount. Enter numeric deposit amount:")
        return

    await state.update_data(new_min_dep=min_dep)
    await state.set_state(AdminChallengeCreateStates.waiting_for_max_slots)
    await message.answer(
        "Step 3 of 3: Enter total participant slots capacity:\n"
        "<i>(Example: 30)</i>",
        parse_mode="HTML"
    )


@router.message(AdminChallengeCreateStates.waiting_for_max_slots)
async def handle_create_max_slots(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """Finalize challenge creation."""
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ Enter a valid integer number of slots:")
        return

    slots = int(raw)
    data = await state.get_data()

    challenge = await ChallengeService.create_challenge(
        session=session,
        name=data["new_name"],
        minimum_deposit=data["new_min_dep"],
        max_slots=slots
    )
    await state.clear()

    await message.answer(
        f"✅ <b>CHALLENGE CREATED!</b>\n\n"
        f"<b>Name:</b> {challenge.name}\n"
        f"<b>Min Deposit:</b> ${challenge.minimum_deposit:.0f}\n"
        f"<b>Slots:</b> {challenge.max_slots}\n"
        f"<b>Status:</b> OPEN\n\n"
        "It is now live on the registration menu.",
        parse_mode="HTML"
    )
