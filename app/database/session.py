from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.database.models import Base

# Configure async engine
# Note: SQLite needs check_same_thread=False; Supabase PgBouncer pooler needs statement_cache_size=0
connect_args = {}
if settings.async_database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
elif "pooler.supabase.com" in settings.async_database_url or ":6543" in settings.async_database_url:
    connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency / generator for database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


from sqlalchemy import text

async def _run_migrations(conn) -> None:
    """Safely apply schema migrations for new columns on SQLite / PostgreSQL."""
    if "sqlite" in settings.async_database_url:
        # Check registrations
        res = await conn.execute(text("PRAGMA table_info(registrations)"))
        cols = {row[1] for row in res.fetchall()}
        if cols:
            if "retry_count" not in cols:
                await conn.execute(text("ALTER TABLE registrations ADD COLUMN retry_count INTEGER DEFAULT 0"))
            if "last_auto_checked_at" not in cols:
                await conn.execute(text("ALTER TABLE registrations ADD COLUMN last_auto_checked_at DATETIME"))

        # Check verification_results
        res_vr = await conn.execute(text("PRAGMA table_info(verification_results)"))
        vr_cols = {row[1] for row in res_vr.fetchall()}
        if vr_cols:
            vr_adds = [
                ("balance", "FLOAT DEFAULT 0.0"),
                ("deposits_count", "INTEGER DEFAULT 0"),
                ("deposits_sum", "FLOAT DEFAULT 0.0"),
                ("bonuses_count", "INTEGER DEFAULT 0"),
                ("bonuses_sum", "FLOAT DEFAULT 0.0"),
                ("withdrawals_count", "INTEGER DEFAULT 0"),
                ("withdrawals_sum", "FLOAT DEFAULT 0.0"),
                ("country", "VARCHAR(100)"),
                ("registration_date", "VARCHAR(50)"),
                ("affiliate_program", "VARCHAR(100)"),
            ]
            for col_name, col_def in vr_adds:
                if col_name not in vr_cols:
                    await conn.execute(text(f"ALTER TABLE verification_results ADD COLUMN {col_name} {col_def}"))


async def init_db() -> None:
    """Create tables, apply migrations, and seed initial data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_migrations(conn)

    # Seed initial data
    from app.database.seed import seed_initial_data
    async with async_session_maker() as session:
        await seed_initial_data(session)
