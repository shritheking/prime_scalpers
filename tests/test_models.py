import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database.models import Base, Participant, Challenge, Registration, RegistrationStatus, VerificationStatus, ChallengeStatus

# In-memory SQLite for isolated tests
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
async def test_create_participant_and_challenge(test_session: AsyncSession):
    participant = Participant(
        telegram_id=987654321,
        username="trader_john",
        full_name="John Trader"
    )
    test_session.add(participant)

    challenge = Challenge(
        name="$100 Scalpers Challenge",
        minimum_deposit=100.0,
        max_slots=10,
        allocated_slots=0,
        status=ChallengeStatus.OPEN
    )
    test_session.add(challenge)
    await test_session.commit()

    assert participant.id is not None
    assert challenge.id is not None
    assert challenge.remaining_slots == 10


@pytest.mark.asyncio
async def test_registration_and_duplicate_prevention(test_session: AsyncSession):
    participant = Participant(telegram_id=123456, full_name="Alpha Trader")
    challenge = Challenge(name="Test Challenge", minimum_deposit=100.0, max_slots=5)
    test_session.add_all([participant, challenge])
    await test_session.commit()

    # First registration
    reg1 = Registration(
        participant_id=participant.id,
        challenge_id=challenge.id,
        quotex_trader_id="2419001",
        account_type="new",
        status=RegistrationStatus.SUBMITTED,
        verification_status=VerificationStatus.PENDING
    )
    test_session.add(reg1)
    await test_session.commit()
    assert reg1.id is not None

    # Duplicate registration attempt for same participant and challenge
    reg2 = Registration(
        participant_id=participant.id,
        challenge_id=challenge.id,
        quotex_trader_id="2419001",
        account_type="new",
        status=RegistrationStatus.SUBMITTED
    )
    test_session.add(reg2)

    with pytest.raises(Exception):
        await test_session.commit()
    await test_session.rollback()
