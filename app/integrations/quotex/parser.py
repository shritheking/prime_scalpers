import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ParsedQuotexTraderData(BaseModel):
    trader_id: str
    country: Optional[str] = None
    registration_date: Optional[str] = None
    affiliate_program: Optional[str] = None
    link_id: Optional[str] = None
    balance: float = 0.0
    deposits_count: int = 0
    deposits_sum: float = 0.0
    bonuses_count: int = 0
    bonuses_sum: float = 0.0
    withdrawals_count: int = 0
    withdrawals_sum: float = 0.0
    is_not_found: bool = False
    raw_text: str = ""


class QuotexPartnerResponseParser:
    """Parses messages returned by @QuotexPartnerBot into structured telemetry."""

    @staticmethod
    def _clean_amount(raw_val: str) -> float:
        """Helper to parse currency strings like '$100.50' or '1,200.00' into float."""
        if not raw_val:
            return 0.0
        # Remove currency symbols and formatting commas
        cleaned = re.sub(r"[^\d.-]", "", raw_val.strip())
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    @classmethod
    def parse(cls, text: str) -> ParsedQuotexTraderData:
        raw_text = text.strip() if text else ""
        if not raw_text:
            return ParsedQuotexTraderData(trader_id="", is_not_found=True, raw_text="")

        # Check for explicit not-found indicators
        not_found_patterns = [
            r"not\s+found",
            r"trader\s+(?:does\s+not\s+exist|not\s+found)",
            r"no\s+trader\s+with\s+(?:id|number)",
            r"invalid\s+trader\s+id"
        ]
        for pattern in not_found_patterns:
            if re.search(pattern, raw_text, re.IGNORECASE):
                return ParsedQuotexTraderData(trader_id="", is_not_found=True, raw_text=raw_text)

        # Extract Trader ID
        # Format example: 'Trader # 95498411' or 'Trader #95498411'
        trader_id_match = re.search(r"Trader\s*#\s*(\d+)", raw_text, re.IGNORECASE)
        trader_id = trader_id_match.group(1) if trader_id_match else ""

        # Country
        country_match = re.search(r"Country:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        country = country_match.group(1).strip() if country_match else None

        # Registration Date (strips optional parentheses)
        reg_date_match = re.search(r"Registration\s*Date:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        registration_date = reg_date_match.group(1).strip(" ()\t\r\n") if reg_date_match else None

        # Affiliate program
        program_match = re.search(r"Affiliate\s*program:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        affiliate_program = program_match.group(1).strip() if program_match else None

        # Link Id
        link_id_match = re.search(r"Link\s*Id:\s*(\w+)", raw_text, re.IGNORECASE)
        link_id = link_id_match.group(1).strip() if link_id_match else None

        # Balance
        balance_match = re.search(r"Balance:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        balance = cls._clean_amount(balance_match.group(1)) if balance_match else 0.0

        # Deposits Count & Sum
        dep_count_match = re.search(r"Deposits\s*Count:\s*(\d+)", raw_text, re.IGNORECASE)
        deposits_count = int(dep_count_match.group(1)) if dep_count_match else 0

        dep_sum_match = re.search(r"Deposits\s*Sum:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        deposits_sum = cls._clean_amount(dep_sum_match.group(1)) if dep_sum_match else 0.0

        # Bonuses Count & Sum
        bon_count_match = re.search(r"Bonuses\s*Count:\s*(\d+)", raw_text, re.IGNORECASE)
        bonuses_count = int(bon_count_match.group(1)) if bon_count_match else 0

        bon_sum_match = re.search(r"Bonuses\s*Sum:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        bonuses_sum = cls._clean_amount(bon_sum_match.group(1)) if bon_sum_match else 0.0

        # Withdrawals Count & Sum
        wd_count_match = re.search(r"Withdrawals\s*Count:\s*(\d+)", raw_text, re.IGNORECASE)
        withdrawals_count = int(wd_count_match.group(1)) if wd_count_match else 0

        wd_sum_match = re.search(r"Withdrawals\s*Sum:\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        withdrawals_sum = cls._clean_amount(wd_sum_match.group(1)) if wd_sum_match else 0.0

        return ParsedQuotexTraderData(
            trader_id=trader_id,
            country=country,
            registration_date=registration_date,
            affiliate_program=affiliate_program,
            link_id=link_id,
            balance=balance,
            deposits_count=deposits_count,
            deposits_sum=deposits_sum,
            bonuses_count=bonuses_count,
            bonuses_sum=bonuses_sum,
            withdrawals_count=withdrawals_count,
            withdrawals_sum=withdrawals_sum,
            is_not_found=False if trader_id else True,
            raw_text=raw_text
        )
