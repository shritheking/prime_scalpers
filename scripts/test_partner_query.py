#!/usr/bin/env python3
"""Test script to verify MTProto connection and query @QuotexPartnerBot."""

import asyncio
import os
import sys

# Ensure project root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure SSL trust on Windows
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

# Ensure event loop for Python 3.14
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from app.config import settings
from app.integrations.quotex.mtproto import PartnerBotMTProtoProvider


async def test_connection():
    print("=" * 60)
    print("TESTING QUOTEX PARTNER BOT MTPROTO INTEGRATION")
    print("=" * 60)

    provider = PartnerBotMTProtoProvider()
    print(f"API ID configured: {bool(provider.api_id)}")
    print(f"API Hash configured: {bool(provider.api_hash)}")
    print(f"Session string configured: {bool(provider.session_string)}")

    if not provider.is_configured:
        print("[ERROR] Provider is not configured. Check .env file.")
        return

    print("\nConnecting to Telegram via Telethon...")
    client = await provider.get_client()
    if not client:
        print("[ERROR] Failed to connect or session is unauthorized.")
        return

    me = await client.get_me()
    print(f"[SUCCESS] Connected as: {me.first_name} (@{me.username}, ID: {me.id})")

    # Test trader ID query
    test_trader_id = "95498411"
    print(f"\nSending test query for Trader ID: {test_trader_id} to @QuotexPartnerBot...")
    result = await provider.verify_trader(test_trader_id)

    print("\n--- QUERY RESULT ---")
    print(f"Trader ID: {result.trader_id}")
    print(f"Status: {result.status.value}")
    print(f"Message: {result.message}")
    print(f"Link ID: {result.affiliate_link_id} (Expected: {settings.QUOTEX_AFFILIATE_LINK_ID})")
    print(f"Affiliate Matched: {result.is_affiliate_matched}")
    print(f"Deposit Amount: ${result.deposit_amount}")
    print(f"Deposit Sufficient: {result.is_deposit_sufficient}")
    print(f"Raw Data: {result.raw_data}")
    print("=" * 60)

    await client.disconnect()


if __name__ == "__main__":
    loop.run_until_complete(test_connection())
