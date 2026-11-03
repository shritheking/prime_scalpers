import json
import logging
from datetime import datetime
from typing import Optional, Tuple
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database.models import (
    Registration, RegistrationStatus, VerificationStatus,
    VerificationRequest, VerificationResult, AuditLog
)
from app.integrations.quotex import get_verification_provider, TraderVerificationResult
from app.integrations.quotex.manual import ManualVerificationProvider
from app.services.challenge import ChallengeService

logger = logging.getLogger(__name__)


class VerificationService:
    """Orchestrates automated and manual Quotex affiliate/deposit verifications."""

    @staticmethod
    async def verify_registration_automated(
        session: AsyncSession,
        registration: Registration,
        bot: Optional[Bot] = None
    ) -> TraderVerificationResult:
        """Execute automated Quotex verification, save telemetry, and trigger automated approval if eligible."""
        challenge = registration.challenge
        participant = registration.participant

        provider = get_verification_provider()
        provider_name = settings.QUOTEX_VERIFICATION_PROVIDER.lower()

        logger.info(f"Running automated verification for Reg #{registration.id} (Trader {registration.quotex_trader_id}) via {provider_name}...")

        effective_min_deposit = 0.0 if settings.MINIMUM_DEPOSIT == 0 else challenge.minimum_deposit

        # 1. Query the provider
        result: TraderVerificationResult = await provider.verify_trader(
            trader_id=registration.quotex_trader_id,
            minimum_deposit=effective_min_deposit,
            expected_affiliate_id=challenge.affiliate_link_id
        )

        # 2. Update registration status & timestamps
        registration.verification_status = result.status
        registration.last_auto_checked_at = datetime.utcnow()
        registration.retry_count += 1

        # 3. Save or update VerificationRequest
        v_req_stmt = (
            select(VerificationRequest)
            .where(VerificationRequest.registration_id == registration.id)
            .order_by(VerificationRequest.requested_at.desc())
        )
        v_req = (await session.execute(v_req_stmt)).scalars().first()
        if not v_req:
            v_req = VerificationRequest(
                registration_id=registration.id,
                provider_name=provider_name,
                status=result.status
            )
            session.add(v_req)
            await session.flush()
        else:
            v_req.status = result.status
            v_req.completed_at = datetime.utcnow()

        # 4. Save detailed telemetry in VerificationResult
        raw_dict = result.raw_data or {}
        v_result = VerificationResult(
            request_id=v_req.id,
            registration_id=registration.id,
            verified_by_admin_id=None,  # Automated
            trader_id=registration.quotex_trader_id,
            affiliate_link_id=result.affiliate_link_id,
            deposit_amount=result.deposit_amount,
            balance=raw_dict.get("balance"),
            deposits_count=raw_dict.get("deposits_count"),
            withdrawals_count=raw_dict.get("withdrawals_count"),
            withdrawals_sum=raw_dict.get("withdrawals_sum"),
            country=raw_dict.get("country"),
            registration_date=raw_dict.get("registration_date"),
            is_affiliate_matched=result.is_affiliate_matched,
            is_deposit_sufficient=result.is_deposit_sufficient,
            raw_evidence=json.dumps(raw_dict) if raw_dict else None,
            notes=result.message,
            created_at=datetime.utcnow()
        )
        session.add(v_result)

        audit = AuditLog(
            admin_telegram_id=0,
            action="AUTO_VERIFY",
            target_type="Registration",
            target_id=str(registration.id),
            details=f"Provider: {provider_name} | Status: {result.status.value} | Dep: ${result.deposit_amount or 0:.2f} | Msg: {result.message}"
        )
        session.add(audit)
        await session.commit()
        await session.refresh(registration)

        # 5. Handle automated actions based on outcome
        if bot:
            await VerificationService._handle_automated_outcome(
                session=session,
                registration=registration,
                result=result,
                bot=bot
            )

        return result

    @staticmethod
    async def _handle_automated_outcome(
        session: AsyncSession,
        registration: Registration,
        result: TraderVerificationResult,
        bot: Bot
    ) -> None:
        """Triggers slot allocation and participant messaging according to verification state."""
        from app.services.invitation import InvitationService

        participant = registration.participant
        challenge = registration.challenge

        if result.status == VerificationStatus.VERIFIED:
            # 1. Fully verified: Automatically allocate slot & send private channel invite!
            alloc_success, alloc_msg, _ = await VerificationService.approve_and_allocate_slot(
                session=session,
                registration_id=registration.id,
                admin_telegram_id=0  # Automated system
            )
            if alloc_success:
                await InvitationService.issue_and_send_invitation(
                    session=session,
                    registration=registration,
                    bot=bot
                )
            else:
                logger.error(f"Slot allocation failed for verified Reg #{registration.id}: {alloc_msg}")
                # Alert admin that slots might be full
                for a_id in settings.admin_ids:
                    try:
                        await bot.send_message(
                            chat_id=a_id,
                            text=f"⚠️ <b>SLOT ALLOCATION ALERT</b>\nParticipant {participant.full_name} is VERIFIED but slot allocation failed: {alloc_msg}",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

        elif result.status == VerificationStatus.DEPOSIT_REQUIRED:
            # 2. Deposit required: Notify participant with direct Check Again button
            curr_dep = result.deposit_amount or 0.0
            min_dep = 0.0 if settings.MINIMUM_DEPOSIT == 0 else challenge.minimum_deposit
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Check Deposit Again", callback_data=f"recheck_deposit:{registration.id}")],
                    [InlineKeyboardButton(text="📋 My Registration Status", callback_data="my_status")],
                    [InlineKeyboardButton(text="💬 Contact Support", callback_data="contact_support")]
                ]
            )
            text = (
                f"⚠️ <b>PRIME SCALPERS • DEPOSIT VERIFICATION UPDATE</b>\n\n"
                f"<b>Challenge:</b> {challenge.name}\n"
                f"<b>Quotex Trader ID:</b> <code>{registration.quotex_trader_id}</code>\n"
                f"<b>Affiliate Link ID:</b> ✅ Matched (<code>{challenge.affiliate_link_id}</code>)\n\n"
                f"<b>Current Verified Deposit:</b> ${curr_dep:.2f} USD\n"
                f"<b>Minimum Required Deposit:</b> ${min_dep:.2f} USD\n\n"
                f"Your account is correctly affiliated! However, channel access requires meeting the ${min_dep:.0f} minimum deposit threshold.\n\n"
                f"<i>Once you have funded your Quotex balance, tap 'Check Deposit Again' below for instant automated re-verification.</i>"
            )
            try:
                await bot.send_message(chat_id=participant.telegram_id, text=text, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Failed to DM participant: {e}")

        elif result.status == VerificationStatus.WRONG_AFFILIATE:
            # 3. Wrong affiliate
            text = (
                f"❌ <b>PRIME SCALPERS • AFFILIATE ATTRIBUTION MISMATCH</b>\n\n"
                f"<b>Challenge:</b> {challenge.name}\n"
                f"<b>Quotex Trader ID:</b> <code>{registration.quotex_trader_id}</code>\n\n"
                f"Our automated verification check determined that this Trader ID is registered under a different referrer, not official Affiliate ID <code>{challenge.affiliate_link_id}</code>.\n\n"
                f"To participate in Prime Scalpers Challenges, please register a new Quotex account using our official link:\n"
                f"<code>{settings.QUOTEX_AFFILIATE_LINK}</code>"
            )
            try:
                await bot.send_message(chat_id=participant.telegram_id, text=text, parse_mode="HTML")
            except Exception:
                pass

        elif result.status == VerificationStatus.NOT_FOUND:
            # 4. Trader not found
            text = (
                f"⚠️ <b>PRIME SCALPERS • TRADER ID NOT FOUND</b>\n\n"
                f"Quotex Trader ID <code>{registration.quotex_trader_id}</code> could not be located in our partner records.\n"
                f"Please verify that you registered under our official partner link: <code>{settings.QUOTEX_AFFILIATE_LINK}</code>"
            )
            try:
                await bot.send_message(chat_id=participant.telegram_id, text=text, parse_mode="HTML")
            except Exception:
                pass

        elif result.status == VerificationStatus.RETRY_PENDING:
            # 5. Service temporarily unavailable / timeout -> keep pending
            logger.info(f"Reg #{registration.id} marked RETRY_PENDING. Background worker will re-attempt.")

    @staticmethod
    async def record_manual_verification(
        session: AsyncSession,
        registration_id: int,
        admin_telegram_id: int,
        observed_affiliate_id: Optional[str],
        observed_deposit: Optional[float],
        notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Registration]]:
        """Record manual verification override by an administrator."""
        stmt = (
            select(Registration)
            .where(Registration.id == registration_id)
            .options(
                selectinload(Registration.challenge),
                selectinload(Registration.participant)
            )
        )
        result = await session.execute(stmt)
        registration = result.scalar_one_or_none()
        if not registration:
            return False, "Registration record not found.", None

        challenge = registration.challenge
        eval_result = ManualVerificationProvider.evaluate_manual_input(
            trader_id=registration.quotex_trader_id,
            observed_affiliate_id=observed_affiliate_id,
            observed_deposit=observed_deposit,
            minimum_deposit=0.0 if settings.MINIMUM_DEPOSIT == 0 else challenge.minimum_deposit,
            expected_affiliate_id=challenge.affiliate_link_id
        )

        registration.verification_status = eval_result.status
        if notes:
            registration.admin_notes = notes

        v_req_stmt = (
            select(VerificationRequest)
            .where(VerificationRequest.registration_id == registration.id)
            .order_by(VerificationRequest.requested_at.desc())
        )
        v_req = (await session.execute(v_req_stmt)).scalars().first()
        if not v_req:
            v_req = VerificationRequest(
                registration_id=registration.id,
                provider_name="manual_override",
                status=eval_result.status
            )
            session.add(v_req)
            await session.flush()
        else:
            v_req.status = eval_result.status
            v_req.completed_at = datetime.utcnow()

        v_result = VerificationResult(
            request_id=v_req.id,
            registration_id=registration.id,
            verified_by_admin_id=admin_telegram_id,
            trader_id=registration.quotex_trader_id,
            affiliate_link_id=observed_affiliate_id,
            deposit_amount=observed_deposit,
            is_affiliate_matched=eval_result.is_affiliate_matched,
            is_deposit_sufficient=eval_result.is_deposit_sufficient,
            notes=notes,
            created_at=datetime.utcnow()
        )
        session.add(v_result)

        audit = AuditLog(
            admin_telegram_id=admin_telegram_id,
            action="MANUAL_OVERRIDE",
            target_type="Registration",
            target_id=str(registration.id),
            details=f"Status: {eval_result.status.value} | Trader: {registration.quotex_trader_id} | Dep: {observed_deposit} | Aff: {observed_affiliate_id}"
        )
        session.add(audit)

        await session.commit()
        await session.refresh(registration)
        return True, eval_result.message, registration

    @staticmethod
    async def approve_and_allocate_slot(
        session: AsyncSession,
        registration_id: int,
        admin_telegram_id: int = 0
    ) -> Tuple[bool, str, Optional[Registration]]:
        """Approve verified participant and reserve challenge slot inside a database transaction."""
        stmt = (
            select(Registration)
            .where(Registration.id == registration_id)
            .options(
                selectinload(Registration.challenge),
                selectinload(Registration.participant)
            )
        )
        result = await session.execute(stmt)
        registration = result.scalar_one_or_none()
        if not registration:
            return False, "Registration not found.", None

        if registration.status == RegistrationStatus.APPROVED:
            return True, "Registration is already approved.", registration

        if registration.verification_status != VerificationStatus.VERIFIED:
            return False, f"Cannot approve registration: Verification status is {registration.verification_status.value}.", registration

        # Reserve slot atomically
        slot_reserved, slot_msg = await ChallengeService.reserve_slot_atomic(
            session=session,
            challenge_id=registration.challenge_id
        )
        if not slot_reserved:
            return False, f"Approval failed: {slot_msg}", registration

        registration.status = RegistrationStatus.APPROVED
        registration.slot_reserved = True

        audit = AuditLog(
            admin_telegram_id=admin_telegram_id,
            action="APPROVE_REGISTRATION",
            target_type="Registration",
            target_id=str(registration.id),
            details=f"Approved participant {registration.participant.full_name} for challenge {registration.challenge.name}"
        )
        session.add(audit)

        await session.commit()
        await session.refresh(registration)
        return True, "Participant approved and challenge slot allocated.", registration

    @staticmethod
    async def reject_registration(
        session: AsyncSession,
        registration_id: int,
        admin_telegram_id: int,
        reason: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Registration]]:
        """Reject participant and release slot if previously reserved."""
        stmt = (
            select(Registration)
            .where(Registration.id == registration_id)
            .options(
                selectinload(Registration.challenge),
                selectinload(Registration.participant)
            )
        )
        result = await session.execute(stmt)
        registration = result.scalar_one_or_none()
        if not registration:
            return False, "Registration not found.", None

        if registration.slot_reserved:
            await ChallengeService.release_slot_atomic(session, registration.challenge_id)
            registration.slot_reserved = False

        registration.status = RegistrationStatus.REJECTED
        registration.verification_status = VerificationStatus.REJECTED
        if reason:
            registration.admin_notes = reason

        audit = AuditLog(
            admin_telegram_id=admin_telegram_id,
            action="REJECT_REGISTRATION",
            target_type="Registration",
            target_id=str(registration.id),
            details=f"Rejected registration #{registration.id}. Reason: {reason or 'No reason provided'}"
        )
        session.add(audit)

        await session.commit()
        await session.refresh(registration)
        return True, "Registration rejected.", registration
