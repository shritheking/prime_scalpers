from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.database.models import Registration, Challenge, RegistrationStatus, VerificationStatus


def get_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Full inline keyboard for the administrator control panel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Dashboard", callback_data="admin_dash_view"),
                InlineKeyboardButton(text="🎯 Challenges", callback_data="admin_challenges_list")
            ],
            [
                InlineKeyboardButton(text="📋 All Registrations", callback_data="admin_reg_page:1:all"),
                InlineKeyboardButton(text="⏳ Pending Review", callback_data="admin_reg_page:1:pending")
            ],
            [
                InlineKeyboardButton(text="✅ Approved", callback_data="admin_reg_page:1:approved"),
                InlineKeyboardButton(text="🔢 Manage Slots", callback_data="admin_slots_manage")
            ],
            [
                InlineKeyboardButton(text="🤖 Auto-Verification", callback_data="admin_auto_settings"),
                InlineKeyboardButton(text="🔄 Batch Re-Check", callback_data="admin_trigger_batch_check")
            ],
            [
                InlineKeyboardButton(text="🔗 Affiliate Settings", callback_data="admin_affiliate_settings"),
                InlineKeyboardButton(text="⚙️ Reg Settings", callback_data="admin_reg_settings")
            ],
            [
                InlineKeyboardButton(text="📡 Channel Management", callback_data="admin_channel_mgmt"),
                InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast_start")
            ],
            [
                InlineKeyboardButton(text="📑 Reports & Export", callback_data="admin_reports_view"),
                InlineKeyboardButton(text="🔍 Search Participant", callback_data="admin_search_start")
            ]
        ]
    )


def get_registration_pagination_keyboard(
    registrations: List[Registration],
    current_page: int,
    total_count: int,
    filter_type: str = "all",
    per_page: int = 5
) -> InlineKeyboardMarkup:
    """Paginated list of registrations with direct detail view buttons."""
    buttons = []
    for r in registrations:
        status_icon = (
            "✅" if r.status == RegistrationStatus.APPROVED
            else "⏳" if r.verification_status == VerificationStatus.PENDING
            else "🔍" if r.verification_status == VerificationStatus.MANUAL_REVIEW
            else "⚠️" if r.verification_status == VerificationStatus.DEPOSIT_REQUIRED
            else "🔄" if r.verification_status == VerificationStatus.RETRY_PENDING
            else "❌"
        )
        p_name = r.participant.full_name[:16] if r.participant else "Unknown"
        text = f"{status_icon} #{r.id} • {p_name} • ID: {r.quotex_trader_id}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"reg_detail:{r.id}")])

    total_pages = max(1, (total_count + per_page - 1) // per_page)
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"admin_reg_page:{current_page - 1}:{filter_type}"))

    nav_row.append(InlineKeyboardButton(text=f"📄 {current_page}/{total_pages}", callback_data="noop"))

    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"admin_reg_page:{current_page + 1}:{filter_type}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_dash_view")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_registration_detail_keyboard(reg_id: int) -> InlineKeyboardMarkup:
    """Action buttons for reviewing a single registration."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 Auto-Verify Now", callback_data=f"admin_verify_auto:{reg_id}"),
                InlineKeyboardButton(text="✅ Approve & Invite", callback_data=f"admin_approve_confirm:{reg_id}")
            ],
            [
                InlineKeyboardButton(text="🔍 Manual Override", callback_data=f"admin_verify_manual:{reg_id}"),
                InlineKeyboardButton(text="📜 History", callback_data=f"admin_verify_hist:{reg_id}")
            ],
            [
                InlineKeyboardButton(text="⚠️ Deposit Required", callback_data=f"admin_mark_deposit:{reg_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"admin_reject_start:{reg_id}")
            ],
            [
                InlineKeyboardButton(text="📋 Back to List", callback_data="admin_reg_page:1:all"),
                InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_dash_view")
            ]
        ]
    )


def get_approval_confirmation_keyboard(reg_id: int) -> InlineKeyboardMarkup:
    """Two-step confirmation before approving and allocating a slot."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ YES, Approve & Issue Invite", callback_data=f"admin_approve_execute:{reg_id}")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data=f"reg_detail:{reg_id}")]
        ]
    )


def get_challenges_management_keyboard(challenges: List[Challenge]) -> InlineKeyboardMarkup:
    """Challenges management keyboard."""
    buttons = []
    for c in challenges:
        status_icon = "🟢" if c.status.value == "OPEN" else "🔴"
        text = f"{status_icon} {c.name} (${c.minimum_deposit:.0f}) • {c.allocated_slots}/{c.max_slots}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"admin_chal_detail:{c.id}")])

    buttons.append([InlineKeyboardButton(text="➕ Create New Challenge", callback_data="admin_chal_create")])
    buttons.append([InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_dash_view")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_challenge_detail_keyboard(challenge_id: int, is_open: bool) -> InlineKeyboardMarkup:
    """Action keyboard for managing an individual challenge."""
    toggle_text = "🔒 Close Registrations" if is_open else "🔓 Open Registrations"
    toggle_action = "close" if is_open else "open"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=toggle_text, callback_data=f"admin_chal_toggle:{challenge_id}:{toggle_action}"),
                InlineKeyboardButton(text="🔢 Change Max Slots", callback_data=f"admin_chal_slots:{challenge_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Challenges List", callback_data="admin_challenges_list")
            ]
        ]
    )


def get_channel_management_keyboard() -> InlineKeyboardMarkup:
    """Private channel management actions."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Test Channel Connection", callback_data="admin_channel_test")],
            [InlineKeyboardButton(text="🛡️ Audit Channel Membership", callback_data="admin_channel_audit")],
            [InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_dash_view")]
        ]
    )


def get_reports_keyboard() -> InlineKeyboardMarkup:
    """Reports screen keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Summary Overview", callback_data="admin_report_summary")],
            [InlineKeyboardButton(text="📥 Download CSV Export", callback_data="admin_report_csv")],
            [InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_dash_view")]
        ]
    )


def get_auto_verification_settings_keyboard() -> InlineKeyboardMarkup:
    """Automated verification settings and toggle."""
    toggle_text = "🔴 Disable Auto-Check" if settings.AUTO_VERIFICATION_ENABLED else "🟢 Enable Auto-Check"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="admin_toggle_auto_verif")],
            [InlineKeyboardButton(text="🔄 Run Immediate Batch Check", callback_data="admin_trigger_batch_check")],
            [InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_dash_view")]
        ]
    )
