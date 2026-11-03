import logging
from typing import List, Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Challenge, ChallengeStatus, Registration, RegistrationStatus

logger = logging.getLogger(__name__)


class ChallengeService:
    """Service for managing challenges and atomic slot allocation."""

    @staticmethod
    async def list_open_challenges(session: AsyncSession) -> List[Challenge]:
        """Fetch all challenges open for registration."""
        stmt = (
            select(Challenge)
            .where(Challenge.status == ChallengeStatus.OPEN)
            .order_by(Challenge.minimum_deposit.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_all_challenges(session: AsyncSession) -> List[Challenge]:
        """Fetch all challenges (including draft and closed)."""
        stmt = select(Challenge).order_by(Challenge.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_challenge_by_id(session: AsyncSession, challenge_id: int) -> Optional[Challenge]:
        """Retrieve challenge by ID."""
        stmt = select(Challenge).where(Challenge.id == challenge_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_challenge(
        session: AsyncSession,
        name: str,
        minimum_deposit: float,
        max_slots: int,
        description: Optional[str] = None,
        affiliate_link_id: str = "2414647",
        invite_expiry_hours: int = 24
    ) -> Challenge:
        """Create a new challenge."""
        challenge = Challenge(
            name=name,
            description=description,
            minimum_deposit=minimum_deposit,
            max_slots=max_slots,
            allocated_slots=0,
            status=ChallengeStatus.OPEN,
            affiliate_link_id=affiliate_link_id,
            invite_expiry_hours=invite_expiry_hours
        )
        session.add(challenge)
        await session.commit()
        await session.refresh(challenge)
        logger.info(f"Created new challenge: {challenge.name} (Slots: {max_slots})")
        return challenge

    @staticmethod
    async def update_challenge_slots(
        session: AsyncSession,
        challenge_id: int,
        new_max_slots: int
    ) -> Tuple[bool, str]:
        """Update max slots, ensuring it is never set below already approved participants."""
        challenge = await ChallengeService.get_challenge_by_id(session, challenge_id)
        if not challenge:
            return False, "Challenge not found."

        if new_max_slots < challenge.allocated_slots:
            return False, (
                f"Cannot reduce maximum slots to {new_max_slots}. "
                f"There are already {challenge.allocated_slots} approved participants."
            )

        challenge.max_slots = new_max_slots
        await session.commit()
        return True, f"Max slots for '{challenge.name}' updated to {new_max_slots}."

    @staticmethod
    async def toggle_challenge_status(
        session: AsyncSession,
        challenge_id: int,
        new_status: ChallengeStatus
    ) -> Optional[Challenge]:
        """Open, close or archive a challenge."""
        challenge = await ChallengeService.get_challenge_by_id(session, challenge_id)
        if challenge:
            challenge.status = new_status
            await session.commit()
            await session.refresh(challenge)
        return challenge

    @staticmethod
    async def delete_challenge(session: AsyncSession, challenge_id: int) -> Tuple[bool, str]:
        """Delete a challenge cohort or archive it if active registrations exist."""
        challenge = await ChallengeService.get_challenge_by_id(session, challenge_id)
        if not challenge:
            return False, "Challenge not found."

        reg_stmt = select(Registration).where(Registration.challenge_id == challenge_id)
        res = await session.execute(reg_stmt)
        regs = res.scalars().all()
        if regs:
            challenge.status = ChallengeStatus.ARCHIVED
            await session.commit()
            return True, f"Challenge '{challenge.name}' has existing participant records. It has been ARCHIVED and hidden from open registration."
        else:
            await session.delete(challenge)
            await session.commit()
            return True, f"Challenge '{challenge.name}' has been permanently deleted."

    @staticmethod
    async def reserve_slot_atomic(
        session: AsyncSession,
        challenge_id: int
    ) -> Tuple[bool, str]:
        """Atomically lock challenge and reserve a slot if available.

        Prevents race conditions and overbooking.
        """
        # Lock challenge row for update
        stmt = (
            select(Challenge)
            .where(Challenge.id == challenge_id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        challenge = result.scalar_one_or_none()

        if not challenge:
            return False, "Challenge not found."

        if challenge.status != ChallengeStatus.OPEN:
            return False, f"Challenge '{challenge.name}' is not currently open for registrations."

        if challenge.allocated_slots >= challenge.max_slots:
            return False, f"All {challenge.max_slots} slots for '{challenge.name}' are completely filled."

        challenge.allocated_slots += 1
        await session.flush()
        return True, "Slot successfully reserved."

    @staticmethod
    async def release_slot_atomic(
        session: AsyncSession,
        challenge_id: int
    ) -> None:
        """Release an allocated slot upon rejection or revocation."""
        stmt = (
            select(Challenge)
            .where(Challenge.id == challenge_id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        challenge = result.scalar_one_or_none()
        if challenge and challenge.allocated_slots > 0:
            challenge.allocated_slots -= 1
            await session.flush()
            logger.info(f"Released slot for challenge {challenge.name}. Now {challenge.allocated_slots}/{challenge.max_slots}")
