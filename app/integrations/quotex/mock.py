from typing import Optional, Dict, Any
from app.config import settings
from app.database.models import VerificationStatus
from app.integrations.quotex.base import QuotexVerificationProvider, TraderVerificationResult


class MockVerificationProvider(QuotexVerificationProvider):
    """Mock verification provider for unit tests and local sandboxing ONLY.

    Guardrail: Raises runtime exception if executed when ENVIRONMENT == 'production'.
    """

    def __init__(self):
        if settings.ENVIRONMENT.lower() == "production":
            raise RuntimeError("CRITICAL SECURITY VIOLATION: MockVerificationProvider cannot be initialized in production.")

        # Preset test profiles
        self.profiles: Dict[str, Dict[str, Any]] = {
            "100001": {"affiliate_id": "2414647", "deposit": 150.0, "status": VerificationStatus.VERIFIED},
            "100002": {"affiliate_id": "9999999", "deposit": 500.0, "status": VerificationStatus.WRONG_AFFILIATE},
            "100003": {"affiliate_id": "2414647", "deposit": 45.0, "status": VerificationStatus.DEPOSIT_REQUIRED},
            "100004": {"affiliate_id": None, "deposit": 0.0, "status": VerificationStatus.NOT_FOUND},
        }

    async def verify_trader(
        self,
        trader_id: str,
        minimum_deposit: float = 100.0,
        expected_affiliate_id: str = "2414647"
    ) -> TraderVerificationResult:
        if settings.ENVIRONMENT.lower() == "production":
            raise RuntimeError("CRITICAL: Mock verification is disabled in production.")

        profile = self.profiles.get(trader_id)
        if not profile:
            # Default mock behavior for arbitrary ID in test mode
            return TraderVerificationResult(
                trader_id=trader_id,
                status=VerificationStatus.MANUAL_REVIEW,
                message="[MOCK] Trader not in preset mocks. Marked for manual review."
            )

        affiliate = profile["affiliate_id"]
        deposit = profile["deposit"]
        is_affiliate_matched = affiliate == expected_affiliate_id
        is_deposit_sufficient = deposit >= minimum_deposit

        if not is_affiliate_matched:
            status = VerificationStatus.WRONG_AFFILIATE
        elif not is_deposit_sufficient:
            status = VerificationStatus.DEPOSIT_REQUIRED
        else:
            status = VerificationStatus.VERIFIED

        return TraderVerificationResult(
            trader_id=trader_id,
            status=status,
            affiliate_link_id=affiliate,
            deposit_amount=deposit,
            is_affiliate_matched=is_affiliate_matched,
            is_deposit_sufficient=is_deposit_sufficient,
            message=f"[MOCK] Evaluated: {status.value}"
        )

    async def get_trader_details(self, trader_id: str) -> Optional[Dict[str, Any]]:
        return self.profiles.get(trader_id)

    async def get_affiliate_link_id(self, trader_id: str) -> Optional[str]:
        profile = self.profiles.get(trader_id)
        return profile["affiliate_id"] if profile else None

    async def get_deposit_amount(self, trader_id: str) -> Optional[float]:
        profile = self.profiles.get(trader_id)
        return profile["deposit"] if profile else None
