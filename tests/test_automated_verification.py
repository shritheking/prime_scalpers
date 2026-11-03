import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.database.models import (
    Base, Participant, Challenge, Registration, RegistrationStatus,
    VerificationStatus, ChallengeStatus
)
from app.services.verification import VerificationService
from app.services.registration import RegistrationService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_session():
    # Force mock verification for unit tests
    settings.QUOTEX_VERIFICATION_PROVIDER = "mock"
    settings.ENVIRONMENT = "development"

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
async def test_auto_verification_verified_flow(test_session: AsyncSession):
    # Setup participant and challenge ($100 minimum)
    p = Participant(telegram_id=99001, full_name="Trader Auto")
    c = Challenge(name="$100 Challenge", minimum_deposit=100.0, max_slots=10, allocated_slots=0, status=ChallengeStatus.OPEN)
    test_session.add_all([p, c])
    await test_session.commit()

    # Create registration with mock verified trader '100001' (deposit = $150, affiliate = 2414647)
    reg, _ = await RegistrationService.create_registration(
        session=test_session,
        participant=p,
        challenge=c,
        quotex_trader_id="100001",
        account_type="new"
    )

    # Mock Bot instance
    mock_bot = MagicMock()
    mock_bot.create_chat_invite_link = AsyncMock()
    mock_invite = MagicMock()
    mock_invite.invite_link = "https://t.me/+prime_test_invite"
    mock_bot.create_chat_invite_link.return_value = mock_invite
    mock_bot.send_message = AsyncMock()

    # Execute automated verification
    result = await VerificationService.verify_registration_automated(
        session=test_session,
        registration=reg,
        bot=mock_bot
    )

    assert result.status == VerificationStatus.VERIFIED
    assert reg.verification_status == VerificationStatus.VERIFIED
    assert reg.status == RegistrationStatus.INVITED
    assert reg.slot_reserved is True
    assert c.allocated_slots == 1


@pytest.mark.asyncio
async def test_auto_verification_deposit_required_flow(test_session: AsyncSession):
    p = Participant(telegram_id=99002, full_name="Trader Low Deposit")
    c = Challenge(name="$100 Challenge", minimum_deposit=100.0, max_slots=10, allocated_slots=0)
    test_session.add_all([p, c])
    await test_session.commit()

    # Create registration with mock trader '100003' (deposit = $45 < $100)
    reg, _ = await RegistrationService.create_registration(
        session=test_session,
        participant=p,
        challenge=c,
        quotex_trader_id="100003",
        account_type="new"
    )

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    result = await VerificationService.verify_registration_automated(
        session=test_session,
        registration=reg,
        bot=mock_bot
    )

    assert result.status == VerificationStatus.DEPOSIT_REQUIRED
    assert reg.verification_status == VerificationStatus.DEPOSIT_REQUIRED
    assert reg.status == RegistrationStatus.SUBMITTED
    assert reg.slot_reserved is False
    assert c.allocated_slots == 0


@pytest.mark.asyncio
async def test_auto_verification_wrong_affiliate_flow(test_session: AsyncSession):
    p = Participant(telegram_id=99003, full_name="Trader Wrong Link")
    c = Challenge(name="$100 Challenge", minimum_deposit=100.0, max_slots=10, allocated_slots=0)
    test_session.add_all([p, c])
    await test_session.commit()

    # Create registration with mock trader '100002' (affiliate = 9999999 != 2414647)
    reg, _ = await RegistrationService.create_registration(
        session=test_session,
        participant=p,
        challenge=c,
        quotex_trader_id="100002",
        account_type="new"
    )

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    result = await VerificationService.verify_registration_automated(
        session=test_session,
        registration=reg,
        bot=mock_bot
    )

    assert result.status == VerificationStatus.WRONG_AFFILIATE
    assert reg.verification_status == VerificationStatus.WRONG_AFFILIATE
    assert reg.slot_reserved is False
    assert c.allocated_slots == 0
