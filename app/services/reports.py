import io
import csv
from typing import Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import (
    Registration, RegistrationStatus, VerificationStatus,
    Challenge, ChallengeStatus, Participant
)


class ReportsService:
    """Generates analytics summaries and exportable CSV reports."""

    @staticmethod
    async def get_dashboard_metrics(session: AsyncSession) -> Dict[str, Any]:
        """Aggregate high-level operational metrics for the admin dashboard."""
        total_regs = (await session.execute(select(func.count(Registration.id)))).scalar() or 0
        pending_regs = (await session.execute(
            select(func.count(Registration.id)).where(Registration.verification_status == VerificationStatus.PENDING)
        )).scalar() or 0
        manual_review = (await session.execute(
            select(func.count(Registration.id)).where(Registration.verification_status == VerificationStatus.MANUAL_REVIEW)
        )).scalar() or 0
        verified_count = (await session.execute(
            select(func.count(Registration.id)).where(Registration.verification_status == VerificationStatus.VERIFIED)
        )).scalar() or 0
        rejected_count = (await session.execute(
            select(func.count(Registration.id)).where(Registration.status == RegistrationStatus.REJECTED)
        )).scalar() or 0
        approved_count = (await session.execute(
            select(func.count(Registration.id)).where(
                Registration.status.in_([RegistrationStatus.APPROVED, RegistrationStatus.INVITED, RegistrationStatus.JOINED])
            )
        )).scalar() or 0
        deposit_required = (await session.execute(
            select(func.count(Registration.id)).where(Registration.verification_status == VerificationStatus.DEPOSIT_REQUIRED)
        )).scalar() or 0

        # Challenges stats
        challenges_stmt = select(Challenge).where(Challenge.status == ChallengeStatus.OPEN)
        open_challenges = list((await session.execute(challenges_stmt)).scalars().all())

        total_max_slots = sum(c.max_slots for c in open_challenges)
        total_alloc_slots = sum(c.allocated_slots for c in open_challenges)
        available_slots = max(0, total_max_slots - total_alloc_slots)

        return {
            "total_registrations": total_regs,
            "pending_verifications": pending_regs,
            "manual_review": manual_review,
            "verified_participants": verified_count,
            "rejected_participants": rejected_count,
            "approved_participants": approved_count,
            "deposit_required": deposit_required,
            "active_challenges_count": len(open_challenges),
            "total_slots": total_max_slots,
            "allocated_slots": total_alloc_slots,
            "available_slots": available_slots,
            "open_challenges": open_challenges
        }

    @staticmethod
    async def generate_markdown_summary(session: AsyncSession) -> str:
        """Formatted operational summary report for Telegram."""
        metrics = await ReportsService.get_dashboard_metrics(session)

        lines = [
            "📊 <b>PRIME SCALPERS OPERATIONAL REPORT</b>",
            "───────────────────────────",
            f"<b>Total Registrations:</b> {metrics['total_registrations']}",
            f"<b>Approved Participants:</b> {metrics['approved_participants']}",
            f"<b>Pending Verifications:</b> {metrics['pending_verifications']}",
            f"<b>In Manual Review:</b> {metrics['manual_review']}",
            f"<b>Awaiting Deposit:</b> {metrics['deposit_required']}",
            f"<b>Rejected:</b> {metrics['rejected_participants']}",
            "",
            "🎯 <b>CHALLENGE & SLOT BREAKDOWN:</b>"
        ]

        for c in metrics["open_challenges"]:
            fill_pct = int((c.allocated_slots / c.max_slots) * 100) if c.max_slots > 0 else 0
            lines.append(
                f"• <b>{c.name}</b> (Min: ${c.minimum_deposit:.0f})\n"
                f"  Slots: {c.allocated_slots}/{c.max_slots} filled ({fill_pct}%) | Left: {c.remaining_slots}"
            )

        lines.append("───────────────────────────")
        return "\n".join(lines)

    @staticmethod
    async def export_registrations_csv(session: AsyncSession) -> str:
        """Generate CSV export of all participant registrations."""
        stmt = (
            select(Registration)
            .options(
                selectinload(Registration.participant),
                selectinload(Registration.challenge)
            )
            .order_by(Registration.created_at.desc())
        )
        regs = list((await session.execute(stmt)).scalars().all())

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Registration ID",
            "Participant Name",
            "Telegram ID",
            "Telegram Username",
            "Quotex Trader ID",
            "Account Type",
            "Challenge Name",
            "Minimum Deposit ($)",
            "Registration Status",
            "Verification Status",
            "Slot Reserved",
            "Admin Notes",
            "Registered At (UTC)"
        ])

        for r in regs:
            writer.writerow([
                r.id,
                r.participant.full_name if r.participant else "",
                r.participant.telegram_id if r.participant else "",
                r.participant.username or "" if r.participant else "",
                r.quotex_trader_id,
                r.account_type,
                r.challenge.name if r.challenge else "",
                r.challenge.minimum_deposit if r.challenge else "",
                r.status.value,
                r.verification_status.value,
                "Yes" if r.slot_reserved else "No",
                r.admin_notes or "",
                r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
            ])

        return output.getvalue()
