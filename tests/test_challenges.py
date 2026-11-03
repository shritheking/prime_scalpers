import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database.models import Base, Challenge, ChallengeStatus
from app.services.challenge import ChallengeService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_slot_overbooking_prevention(test_session: AsyncSession):
    challenge = await ChallengeService.create_challenge(
        session=test_session,
        name="Micro Tier",
        minimum_deposit=100.0,
        max_slots=2
    )

    # Reserve slot 1
    success1, msg1 = await ChallengeService.reserve_slot_atomic(test_session, challenge.id)
    assert success1 is True

    # Reserve slot 2
    success2, msg2 = await ChallengeService.reserve_slot_atomic(test_session, challenge.id)
    assert success2 is True

    # Attempt to reserve slot 3 (overbooking attempt)
    success3, msg3 = await ChallengeService.reserve_slot_atomic(test_session, challenge.id)
    assert success3 is False
    assert "filled" in msg3.lower()

    # Release a slot
    await ChallengeService.release_slot_atomic(test_session, challenge.id)
    await test_session.commit()

    # Now reserving slot again should succeed
    success4, _ = await ChallengeService.reserve_slot_atomic(test_session, challenge.id)
    assert success4 is True


@pytest.mark.asyncio
async def test_cannot_reduce_slots_below_allocated(test_session: AsyncSession):
    challenge = await ChallengeService.create_challenge(
        session=test_session,
        name="Scaling Tier",
        minimum_deposit=500.0,
        max_slots=10
    )

    # Allocate 5 slots
    for _ in range(5):
        await ChallengeService.reserve_slot_atomic(test_session, challenge.id)
    await test_session.commit()

    # Attempt to reduce max slots to 3 (less than 5 allocated)
    success, msg = await ChallengeService.update_challenge_slots(test_session, challenge.id, 3)
    assert success is False
    assert "already 5 approved" in msg

    # Increasing or setting to 6 should succeed
    success_ok, _ = await ChallengeService.update_challenge_slots(test_session, challenge.id, 6)
    assert success_ok is True
