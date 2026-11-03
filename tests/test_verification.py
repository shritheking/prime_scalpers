import pytest
from app.database.models import VerificationStatus
from app.integrations.quotex.manual import ManualVerificationProvider
from app.integrations.quotex.mock import MockVerificationProvider


def test_manual_verification_evaluation():
    # 1. Matching affiliate + sufficient deposit -> VERIFIED
    res = ManualVerificationProvider.evaluate_manual_input(
        trader_id="12345",
        observed_affiliate_id="2414647",
        observed_deposit=150.0,
        minimum_deposit=100.0,
        expected_affiliate_id="2414647"
    )
    assert res.status == VerificationStatus.VERIFIED
    assert res.is_affiliate_matched is True
    assert res.is_deposit_sufficient is True

    # 2. Matching affiliate + insufficient deposit -> DEPOSIT_REQUIRED
    res_dep = ManualVerificationProvider.evaluate_manual_input(
        trader_id="12345",
        observed_affiliate_id="2414647",
        observed_deposit=40.0,
        minimum_deposit=100.0,
        expected_affiliate_id="2414647"
    )
    assert res_dep.status == VerificationStatus.DEPOSIT_REQUIRED
    assert res_dep.is_affiliate_matched is True
    assert res_dep.is_deposit_sufficient is False

    # 3. Wrong affiliate -> WRONG_AFFILIATE
    res_aff = ManualVerificationProvider.evaluate_manual_input(
        trader_id="12345",
        observed_affiliate_id="999888",
        observed_deposit=200.0,
        minimum_deposit=100.0,
        expected_affiliate_id="2414647"
    )
    assert res_aff.status == VerificationStatus.WRONG_AFFILIATE
    assert res_aff.is_affiliate_matched is False

    # 4. Not found in records -> NOT_FOUND
    res_nf = ManualVerificationProvider.evaluate_manual_input(
        trader_id="12345",
        observed_affiliate_id=None,
        observed_deposit=None,
        minimum_deposit=100.0,
        expected_affiliate_id="2414647"
    )
    assert res_nf.status == VerificationStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_mock_verification_provider():
    provider = MockVerificationProvider()

    # Pre-configured mock trader 100001 (verified)
    res = await provider.verify_trader(trader_id="100001", minimum_deposit=100.0, expected_affiliate_id="2414647")
    assert res.status == VerificationStatus.VERIFIED

    # Pre-configured mock trader 100002 (wrong affiliate)
    res2 = await provider.verify_trader(trader_id="100002", minimum_deposit=100.0, expected_affiliate_id="2414647")
    assert res2.status == VerificationStatus.WRONG_AFFILIATE

    # Pre-configured mock trader 100003 (deposit required)
    res3 = await provider.verify_trader(trader_id="100003", minimum_deposit=100.0, expected_affiliate_id="2414647")
    assert res3.status == VerificationStatus.DEPOSIT_REQUIRED
