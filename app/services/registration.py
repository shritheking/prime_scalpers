import logging
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import (
    Participant, Challenge, Registration, RegistrationStatus,
    VerificationStatus, VerificationRequest
)

logger = logging.getLogger(__name__)


class RegistrationService:
    """Handles participant lifecycle, challenge enrollment, and duplicate prevention."""

    @staticmethod
    async def get_or_create_participant(
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str],
        full_name: str
    ) -> Participant:
        """Find participant by Telegram ID or create new record."""
        stmt = select(Participant).where(Participant.telegram_id == telegram_id)
        result = await session.execute(stmt)
        participant = result.scalar_one_or_none()

        if not participant:
            participant = Participant(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name
            )
            session.add(participant)
            await session.commit()
            await session.refresh(participant)
            logger.info(f"Registered new participant: {full_name} ({telegram_id})")
        else:
            # Update latest username or full_name if changed
            if participant.username != username or participant.full_name != full_name:
                participant.username = username
                participant.full_name = full_name
                await session.commit()

        return participant

    @staticmethod
    async def check_duplicate_registration(
        session: AsyncSession,
        participant_id: int,
        challenge_id: int
    ) -> Optional[Registration]:
        """Check if participant is already registered for this specific challenge."""
        stmt = select(Registration).where(
            and_(
                Registration.participant_id == participant_id,
                Registration.challenge_id == challenge_id
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_registration(
        session: AsyncSession,
        participant: Participant,
        challenge: Challenge,
        quotex_trader_id: str,
        account_type: str
    ) -> Tuple[Optional[Registration], str]:
        """Create new challenge registration with duplicate prevention."""
        existing = await RegistrationService.check_duplicate_registration(
            session=session,
            participant_id=participant.id,
            challenge_id=challenge.id
        )
        if existing:
            return None, f"You are already registered for {challenge.name} (Status: {existing.status.value})."

        # Initialize registration record
        registration = Registration(
            participant_id=participant.id,
            challenge_id=challenge.id,
            quotex_trader_id=str(quotex_trader_id).strip(),
            account_type=account_type,
            status=RegistrationStatus.SUBMITTED,
            verification_status=VerificationStatus.PENDING,
            slot_reserved=False
        )
        session.add(registration)
        await session.flush()

        # Create linked verification request
        v_req = VerificationRequest(
            registration_id=registration.id,
            provider_name="manual",
            status=VerificationStatus.PENDING
        )
        session.add(v_req)

        await session.commit()
        await session.refresh(registration)
        logger.info(f"Created registration #{registration.id} for Trader ID {quotex_trader_id}")
        return registration, "Registration submitted successfully."

    @staticmethod
    async def get_participant_registrations(
        session: AsyncSession,
        telegram_id: int
    ) -> List[Registration]:
        """Fetch all registrations for a given Telegram user ID with challenge details."""
        stmt = (
            select(Registration)
            .join(Participant)
            .where(Participant.telegram_id == telegram_id)
            .options(
                selectinload(Registration.challenge),
                selectinload(Registration.participant)
            )
            .order_by(Registration.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_registration_by_id(
        session: AsyncSession,
        registration_id: int
    ) -> Optional[Registration]:
        """Get registration with eager-loaded relations."""
        stmt = (
            select(Registration)
            .where(Registration.id == registration_id)
            .options(
                selectinload(Registration.participant),
                selectinload(Registration.challenge),
                selectinload(Registration.invite_links),
                selectinload(Registration.verification_requests)
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def search_registrations(
        session: AsyncSession,
        query: str
    ) -> List[Registration]:
        """Search registrations by Quotex Trader ID, Telegram ID, or Username."""
        query_str = query.strip()
        conditions = [Registration.quotex_trader_id.ilike(f"%{query_str}%")]

        if query_str.isdigit():
            conditions.append(Participant.telegram_id == int(query_str))
        else:
            conditions.append(Participant.username.ilike(f"%{query_str}%"))
            conditions.append(Participant.full_name.ilike(f"%{query_str}%"))

        stmt = (
            select(Registration)
            .join(Participant)
            .where(or_(*conditions))
            .options(
                selectinload(Registration.participant),
                selectinload(Registration.challenge)
            )
            .order_by(Registration.created_at.desc())
            .limit(20)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_paginated_registrations(
        session: AsyncSession,
        page: int = 1,
        per_page: int = 5,
        filter_status: Optional[RegistrationStatus] = None,
        filter_verification: Optional[VerificationStatus] = None
    ) -> Tuple[List[Registration], int]:
        """Fetch paginated list of registrations with total count."""
        conditions = []
        if filter_status:
            conditions.append(Registration.status == filter_status)
        if filter_verification:
            conditions.append(Registration.verification_status == filter_verification)

        count_stmt = select(func.count(Registration.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_count = (await session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Registration)
            .options(
                selectinload(Registration.participant),
                selectinload(Registration.challenge)
            )
            .order_by(Registration.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await session.execute(stmt)
        return list(result.scalars().all()), total_count
