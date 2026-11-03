from app.config import settings
from app.integrations.quotex.base import QuotexVerificationProvider, TraderVerificationResult
from app.integrations.quotex.manual import ManualVerificationProvider
from app.integrations.quotex.mock import MockVerificationProvider
from app.integrations.quotex.official import OfficialQuotexProvider
from app.integrations.quotex.mtproto import PartnerBotMTProtoProvider
from app.integrations.quotex.parser import QuotexPartnerResponseParser, ParsedQuotexTraderData

OfficialAPIProvider = OfficialQuotexProvider

# Global singleton instance for MTProto provider to preserve connection and event loops
_mtproto_instance = None


def get_verification_provider() -> QuotexVerificationProvider:
    """Factory to retrieve configured Quotex verification provider."""
    global _mtproto_instance
    provider_name = settings.QUOTEX_VERIFICATION_PROVIDER.lower().strip()

    if provider_name == "mtproto":
        if _mtproto_instance is None:
            _mtproto_instance = PartnerBotMTProtoProvider(
                api_id=settings.TELEGRAM_API_ID,
                api_hash=settings.TELEGRAM_API_HASH,
                session_string=settings.TELEGRAM_SESSION_STRING,
                partner_bot_username=settings.QUOTEX_PARTNER_BOT_USERNAME
            )
        return _mtproto_instance
    elif provider_name == "mock":
        return MockVerificationProvider()
    elif provider_name == "official":
        return OfficialAPIProvider()
    return ManualVerificationProvider()


__all__ = [
    "QuotexVerificationProvider",
    "TraderVerificationResult",
    "ManualVerificationProvider",
    "MockVerificationProvider",
    "OfficialQuotexProvider",
    "OfficialAPIProvider",
    "PartnerBotMTProtoProvider",
    "QuotexPartnerResponseParser",
    "ParsedQuotexTraderData",
    "get_verification_provider",
]
