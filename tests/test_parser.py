import pytest
from app.integrations.quotex.parser import QuotexPartnerResponseParser


def test_parser_with_user_exact_example():
    sample_response = """
Trader # 95498411
Country: India
Registration Date: 03.11.2026
Affiliate program: Turnover 2.0%
Link Id: 2414647

Balance: $0.00
Deposits Count: 0
Deposits Sum: $0.00
Bonuses Count: 0
Bonuses Sum: $0.00
Withdrawals Count: 0
Withdrawals Sum: $0.00
"""
    data = QuotexPartnerResponseParser.parse(sample_response)

    assert data.trader_id == "95498411"
    assert data.country == "India"
    assert data.registration_date == "03.11.2026"
    assert data.affiliate_program == "Turnover 2.0%"
    assert data.link_id == "2414647"
    assert data.balance == 0.0
    assert data.deposits_count == 0
    assert data.deposits_sum == 0.0
    assert data.is_not_found is False


def test_parser_with_funded_trader():
    sample_response = """
Trader # 88291034
Country: United Kingdom
Registration Date: 15.10.2026
Affiliate program: Turnover 2.5%
Link Id: 2414647

Balance: $125.50
Deposits Count: 2
Deposits Sum: $250.00
Bonuses Count: 1
Bonuses Sum: $50.00
Withdrawals Count: 1
Withdrawals Sum: $75.00
"""
    data = QuotexPartnerResponseParser.parse(sample_response)

    assert data.trader_id == "88291034"
    assert data.country == "United Kingdom"
    assert data.link_id == "2414647"
    assert data.balance == 125.50
    assert data.deposits_count == 2
    assert data.deposits_sum == 250.00
    assert data.withdrawals_sum == 75.00
    assert data.is_not_found is False


def test_parser_not_found():
    sample = "Trader not found in partner database."
    data = QuotexPartnerResponseParser.parse(sample)
    assert data.is_not_found is True
