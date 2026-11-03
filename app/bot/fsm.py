from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """FSM states for the participant registration wizard."""
    selecting_challenge = State()
    choosing_account_type = State()
    viewing_affiliate_notice = State()
    entering_trader_id = State()
    confirming_submission = State()


class AdminSearchStates(StatesGroup):
    """FSM states for searching registrations."""
    waiting_for_query = State()


class AdminManualVerifyStates(StatesGroup):
    """FSM states for administrator manual inspection."""
    waiting_for_affiliate_id = State()
    waiting_for_deposit_amount = State()
    waiting_for_notes = State()


class AdminChallengeCreateStates(StatesGroup):
    """FSM states for creating a new challenge."""
    waiting_for_name = State()
    waiting_for_min_deposit = State()
    waiting_for_max_slots = State()
    waiting_for_description = State()


class AdminChallengeEditSlotsStates(StatesGroup):
    """FSM states for editing maximum slots."""
    waiting_for_new_slots = State()


class AdminBroadcastStates(StatesGroup):
    """FSM states for sending a broadcast message."""
    waiting_for_text = State()
    confirming_broadcast = State()


class AdminRejectStates(StatesGroup):
    """FSM states for rejecting a registration with reason."""
    waiting_for_reason = State()
