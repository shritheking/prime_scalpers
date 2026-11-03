import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database.models import Base, Challenge, RegistrationStatus, VerificationStatus
from app.services.registration import RegistrationService

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
async def test_registration_lifecycle(test_session: AsyncSession):
    participant = await RegistrationService.get_or_create_participant(
        session=test_session,
        telegram_id=444555,
        username="scalper_pro",
        full_name="Pro Scalper"
    )
    assert participant.id is not None
    assert participant.telegram_id == 444555

    challenge = Challenge(
        name="$100 Entry Challenge",
        minimum_deposit=100.0,
        max_slots=20
    )
    test_session.add(challenge)
    await test_session.commit()

    # Create registration
    reg, msg = await RegistrationService.create_registration(
        session=test_session,
        participant=participant,
        challenge=challenge,
        quotex_trader_id="998877",
        account_type="new"
    )
    assert reg is not None
    assert reg.status == RegistrationStatus.SUBMITTED
    assert reg.verification_status == VerificationStatus.PENDING

    # Attempt duplicate registration for same participant & challenge
    duplicate, dup_msg = await RegistrationService.create_registration(
        session=test_session,
        participant=participant,
        challenge=challenge,
        quotex_trader_id="998877",
        account_type="new"
    )
    assert duplicate is None
    assert "already registered" in dup_msg.lower()
