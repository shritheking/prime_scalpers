import pytest
import pytest_asyncio
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.bot.filters.admin import IsAdminFilter
from app.database.models import Base, Participant, Challenge, Registration, RegistrationStatus, VerificationStatus
from app.services.reports import ReportsService

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
async def test_admin_filter_authorization():
    admin_filter = IsAdminFilter()

    # Authorized admin message
    admin_msg = MagicMock()
    admin_msg.from_user.id = 5188160752
    assert await admin_filter(admin_msg) is True

    # Unauthorized user message
    unauth_msg = MagicMock()
    unauth_msg.from_user.id = 999999999
    assert await admin_filter(unauth_msg) is False


@pytest.mark.asyncio
async def test_reports_service_aggregation_and_csv(test_session: AsyncSession):
    # Setup test data
    p = Participant(telegram_id=111222, full_name="Metrics Trader")
    c = Challenge(name="Metrics Challenge", minimum_deposit=100.0, max_slots=10, allocated_slots=1)
    test_session.add_all([p, c])
    await test_session.commit()

    reg = Registration(
        participant_id=p.id,
        challenge_id=c.id,
        quotex_trader_id="12345678",
        status=RegistrationStatus.APPROVED,
        verification_status=VerificationStatus.VERIFIED,
        slot_reserved=True
    )
    test_session.add(reg)
    await test_session.commit()

    # Test metrics aggregation
    metrics = await ReportsService.get_dashboard_metrics(test_session)
    assert metrics["total_registrations"] == 1
    assert metrics["approved_participants"] == 1
    assert metrics["verified_participants"] == 1

    # Test CSV generation
    csv_text = await ReportsService.export_registrations_csv(test_session)
    assert "Registration ID" in csv_text
    assert "Metrics Trader" in csv_text
    assert "12345678" in csv_text
