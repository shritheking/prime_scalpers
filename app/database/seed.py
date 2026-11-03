import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database.models import Challenge, ChallengeStatus, Admin, SystemSetting

logger = logging.getLogger(__name__)


async def seed_initial_data(session: AsyncSession) -> None:
    """Seed initial challenges, admin records, and system settings if not already present."""
    # 1. Seed Initial Challenges ($100, $500, $1,000)
    challenges_to_seed = [
        {
            "name": "$100 Challenge",
            "description": "Introductory scalping challenge designed for high-discipline traders. Minimum deposit of $100 via official affiliate link.",
            "minimum_deposit": 100.0,
            "max_slots": 50,
            "status": ChallengeStatus.OPEN,
            "affiliate_link_id": settings.QUOTEX_AFFILIATE_LINK_ID,
            "invite_expiry_hours": 24,
        },
        {
            "name": "$500 Challenge",
            "description": "Intermediate scalping tier with premium community access and direct market discussion. Minimum deposit of $500.",
            "minimum_deposit": 500.0,
            "max_slots": 25,
            "status": ChallengeStatus.OPEN,
            "affiliate_link_id": settings.QUOTEX_AFFILIATE_LINK_ID,
            "invite_expiry_hours": 24,
        },
        {
            "name": "$1,000 Challenge",
            "description": "Elite high-frequency scalpers group with priority analysis and one-on-one trade reviews. Minimum deposit of $1,000.",
            "minimum_deposit": 1000.0,
            "max_slots": 10,
            "status": ChallengeStatus.OPEN,
            "affiliate_link_id": settings.QUOTEX_AFFILIATE_LINK_ID,
            "invite_expiry_hours": 24,
        },
    ]

    for c_data in challenges_to_seed:
        stmt = select(Challenge).where(Challenge.name == c_data["name"])
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            challenge = Challenge(**c_data)
            session.add(challenge)
            logger.info(f"Seeded challenge: {c_data['name']}")

    # 2. Seed Default Admins from settings
    for admin_id in settings.admin_ids:
        stmt = select(Admin).where(Admin.telegram_id == admin_id)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            admin = Admin(
                telegram_id=admin_id,
                username="PrimaryAdmin",
                full_name="Prime Scalpers Admin",
                is_super_admin=True,
                is_active=True
            )
            session.add(admin)
            logger.info(f"Seeded admin Telegram ID: {admin_id}")

    # 3. Seed System Settings
    initial_settings = [
        ("quotex_affiliate_link", settings.QUOTEX_AFFILIATE_LINK, "Official Quotex affiliate registration link"),
        ("quotex_affiliate_link_id", settings.QUOTEX_AFFILIATE_LINK_ID, "Official affiliate tracking ID"),
        ("minimum_deposit", str(settings.MINIMUM_DEPOSIT), "Global minimum deposit USD threshold"),
        ("invite_expiry_hours", str(settings.DEFAULT_INVITE_EXPIRY_HOURS), "Default invite link expiry duration in hours"),
        ("verification_provider", settings.QUOTEX_VERIFICATION_PROVIDER, "Active Quotex verification provider (manual/mock/official)"),
    ]

    for key, value, desc in initial_settings:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            setting = SystemSetting(key=key, value=value, description=desc)
            session.add(setting)

    await session.commit()
    logger.info("Database seeding completed.")
