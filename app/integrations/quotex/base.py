from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.database.models import VerificationStatus


class TraderVerificationResult(BaseModel):
    trader_id: str
    status: VerificationStatus
    affiliate_link_id: Optional[str] = None
    deposit_amount: Optional[float] = None
    is_affiliate_matched: bool = False
    is_deposit_sufficient: bool = False
    raw_data: Optional[Dict[str, Any]] = None
    message: str = ""


class QuotexVerificationProvider(ABC):
    """Abstract base class for modular Quotex verification providers."""

    @abstractmethod
    async def verify_trader(
        self,
        trader_id: str,
        minimum_deposit: float = 100.0,
        expected_affiliate_id: str = "2414647"
    ) -> TraderVerificationResult:
        """Execute full verification pipeline for a Trader ID."""
        pass

    @abstractmethod
    async def get_trader_details(self, trader_id: str) -> Optional[Dict[str, Any]]:
        """Fetch trader metadata if available."""
        pass

    @abstractmethod
    async def get_affiliate_link_id(self, trader_id: str) -> Optional[str]:
        """Fetch affiliated referrer ID for trader."""
        pass

    @abstractmethod
    async def get_deposit_amount(self, trader_id: str) -> Optional[float]:
        """Fetch total deposited amount in USD."""
        pass
