from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import settings
from app.database.models import Challenge


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Main start screen inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Register for Challenge", callback_data="start_register")],
            [InlineKeyboardButton(text="📋 My Registration Status", callback_data="my_status")],
            [
                InlineKeyboardButton(text="💬 Support", callback_data="contact_support"),
                InlineKeyboardButton(text="⚡ Developed by NextGen", url="https://t.me/shridharsan1")
            ]
        ]
    )


def get_challenge_selection_keyboard(challenges: List[Challenge]) -> InlineKeyboardMarkup:
    """Inline keyboard listing available challenges and remaining slots."""
    buttons = []
    for c in challenges:
        slots_text = f"{c.remaining_slots} slots left" if c.remaining_slots > 0 else "FULL"
        text = f"{c.name} (Min: ${c.minimum_deposit:.0f}) • {slots_text}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"select_challenge:{c.id}")])

    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_to_start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_account_type_keyboard() -> InlineKeyboardMarkup:
    """Choose between new or existing Quotex account."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Create Quotex Account", callback_data="acct_new")],
            [InlineKeyboardButton(text="🔑 Already Have an Account", callback_data="acct_existing")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="start_register")]
        ]
    )


def get_affiliate_notice_keyboard(affiliate_url: str) -> InlineKeyboardMarkup:
    """Prompts participant with official link before collecting Trader ID."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Open Official Affiliate Link", url=affiliate_url)],
            [InlineKeyboardButton(text="✍️ I Have Registered, Enter Trader ID", callback_data="enter_trader_id_now")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_account_type")]
        ]
    )


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Final submission confirmation inline keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Submit Registration", callback_data="submit_reg_confirmed")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_to_start")]
        ]
    )


def get_status_action_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for status screen."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh Status", callback_data="my_status")],
            [InlineKeyboardButton(text="🚀 Register Another Challenge", callback_data="start_register")],
            [InlineKeyboardButton(text="💬 Support", callback_data="contact_support")]
        ]
    )
