from typing import List, Set, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Bot
    BOT_TOKEN: str = Field(..., description="Telegram bot API token")
    TELEGRAM_CHANNEL_ID: int = Field(-1003957867906, description="Target private Telegram channel ID")
    ADMIN_TELEGRAM_IDS: str = Field("5188160752", description="Comma-separated Telegram IDs of admins")

    # Quotex Affiliate Config
    QUOTEX_AFFILIATE_LINK: str = Field("https://broker-qx.pro/?lid=2414647", description="Official Quotex affiliate link")
    QUOTEX_AFFILIATE_LINK_ID: str = Field("2414647", description="Affiliate tracking ID to verify")
    MINIMUM_DEPOSIT: float = Field(100.0, description="Minimum USD deposit required for challenge eligibility")

    # Automated Verification & MTProto
    QUOTEX_VERIFICATION_PROVIDER: str = Field("mtproto", description="Active provider: 'mtproto', 'official', 'mock', or 'manual'")
    TELEGRAM_API_ID: Optional[int] = Field(None, description="Telegram application API ID for MTProto client")
    TELEGRAM_API_HASH: Optional[str] = Field(None, description="Telegram application API Hash for MTProto client")
    TELEGRAM_SESSION_STRING: Optional[str] = Field(None, description="Telethon StringSession for partner bot automation")
    QUOTEX_PARTNER_BOT_USERNAME: str = Field("QuotexPartnerBot", description="Quotex Partner Bot username")
    AUTO_VERIFICATION_ENABLED: bool = Field(True, description="Whether to automatically query verification provider upon registration")
    AUTO_RETRY_INTERVAL_MINUTES: int = Field(15, description="Minutes between background re-checks for pending accounts")
    MAX_AUTO_RETRIES: int = Field(5, description="Maximum automated verification retries before requiring manual review")

    # Database
    DATABASE_URL: str = Field("sqlite+aiosqlite:///./prime_scalpers.db", description="Async SQLAlchemy database URL")
    SUPABASE_URL: str = Field("", description="Supabase project URL (optional)")
    SUPABASE_SERVICE_ROLE_KEY: str = Field("", description="Supabase service role key (optional)")

    # Runtime & Deployment
    ENVIRONMENT: str = Field("development", description="development / production / testing")
    PORT: int = Field(8000, description="Health check / server port")
    HOST: str = Field("0.0.0.0", description="Bind host")
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    DEFAULT_INVITE_EXPIRY_HOURS: int = Field(24, description="Hours before single-use invite expires")

    @property
    def admin_ids(self) -> Set[int]:
        """Parsed set of admin Telegram IDs."""
        ids: Set[int] = set()
        for raw in str(self.ADMIN_TELEGRAM_IDS).split(","):
            raw_clean = raw.strip()
            if raw_clean.isdigit() or (raw_clean.startswith("-") and raw_clean[1:].isdigit()):
                ids.add(int(raw_clean))
        return ids

    @property
    def async_database_url(self) -> str:
        """Resolve database URL for async SQLAlchemy."""
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        if self.DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in self.DATABASE_URL:
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DATABASE_URL


settings = Settings()
