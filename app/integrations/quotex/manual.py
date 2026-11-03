from typing import Optional, Dict, Any
from app.database.models import VerificationStatus
from app.integrations.quotex.base import QuotexVerificationProvider, TraderVerificationResult


class ManualVerificationProvider(QuotexVerificationProvider):
    """Provider for manual administrator-driven verification.

    Routes trader submissions to the Telegram Admin queue for manual inspection
    against the official Quotex affiliate partner portal.
    """

    async def verify_trader(
        self,
        trader_id: str,
        minimum_deposit: float = 100.0,
        expected_affiliate_id: str = "2414647"
    ) -> TraderVerificationResult:
        # Standard automated check routes to manual review queue
        return TraderVerificationResult(
            trader_id=trader_id,
            status=VerificationStatus.MANUAL_REVIEW,
            affiliate_link_id=None,
            deposit_amount=None,
            is_affiliate_matched=False,
            is_deposit_sufficient=False,
            message="Queued for manual inspection by Prime Scalpers compliance team."
        )

    async def get_trader_details(self, trader_id: str) -> Optional[Dict[str, Any]]:
        return None

    async def get_affiliate_link_id(self, trader_id: str) -> Optional[str]:
        return None

    async def get_deposit_amount(self, trader_id: str) -> Optional[float]:
        return None

    @staticmethod
    def evaluate_manual_input(
        trader_id: str,
        observed_affiliate_id: Optional[str],
        observed_deposit: Optional[float],
        minimum_deposit: float,
        expected_affiliate_id: str
    ) -> TraderVerificationResult:
        """Deterministic evaluation of administrator manual input."""
        if not observed_affiliate_id and observed_deposit is None:
            return TraderVerificationResult(
                trader_id=trader_id,
                status=VerificationStatus.NOT_FOUND,
                message="Trader ID could not be located in Quotex partner records."
            )

        is_affiliate_matched = str(observed_affiliate_id).strip() == str(expected_affiliate_id).strip()
        deposit = observed_deposit if observed_deposit is not None else 0.0
        is_deposit_sufficient = deposit >= minimum_deposit

        if not is_affiliate_matched:
            return TraderVerificationResult(
                trader_id=trader_id,
                status=VerificationStatus.WRONG_AFFILIATE,
                affiliate_link_id=observed_affiliate_id,
                deposit_amount=deposit,
                is_affiliate_matched=False,
                is_deposit_sufficient=is_deposit_sufficient,
                message=f"Trader registered under different affiliate ({observed_affiliate_id}), expected {expected_affiliate_id}."
            )

        if not is_deposit_sufficient:
            return TraderVerificationResult(
                trader_id=trader_id,
                status=VerificationStatus.DEPOSIT_REQUIRED,
                affiliate_link_id=observed_affiliate_id,
                deposit_amount=deposit,
                is_affiliate_matched=True,
                is_deposit_sufficient=False,
                message=f"Deposit ${deposit:.2f} is below minimum requirement of ${minimum_deposit:.2f}."
            )

        return TraderVerificationResult(
            trader_id=trader_id,
            status=VerificationStatus.VERIFIED,
            affiliate_link_id=observed_affiliate_id,
            deposit_amount=deposit,
            is_affiliate_matched=True,
            is_deposit_sufficient=True,
            message="Affiliate link ID and minimum deposit verified."
        )
