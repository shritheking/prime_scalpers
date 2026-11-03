#!/usr/bin/env python3
"""Interactive setup script for generating Telethon MTProto StringSession.

Run this script to authenticate your affiliate Telegram account
which has access to @QuotexPartnerBot.

Compatible with Python 3.12, 3.13, and 3.14.
"""

import os
import sys
import asyncio

# Ensure SSL trust on Windows / cross-platform
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

# Ensure explicit event loop for Python 3.12+ / 3.14+
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError


async def run_auth():
    print("=" * 60)
    print("PRIME SCALPERS • MTPROTO SESSION SETUP WIZARD")
    print("=" * 60)
    print("This wizard generates a secure Telethon StringSession to enable")
    print("automated queries to @QuotexPartnerBot.\n")

    default_api_id = "24697725"
    default_api_hash = "2147b12e27c3b9b8880c1c2353be966f"

    api_id_input = input(f"Enter your Telegram API_ID [{default_api_id}]: ").strip()
    api_id_str = api_id_input if api_id_input else default_api_id
    if not api_id_str.isdigit():
        print("❌ Invalid API ID. Must be numeric.")
        sys.exit(1)
    api_id = int(api_id_str)

    api_hash_input = input(f"Enter your Telegram API_HASH [{default_api_hash}]: ").strip()
    api_hash = api_hash_input if api_hash_input else default_api_hash
    if not api_hash:
        print("❌ Invalid API HASH.")
        sys.exit(1)

    print("\nConnecting to Telegram DC...")
    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)
    await client.connect()

    phone = input("\nEnter your affiliate Telegram phone number (e.g. +919876543210): ").strip()
    if not phone:
        print("❌ Phone number cannot be empty.")
        await client.disconnect()
        sys.exit(1)

    print(f"Sending login code to {phone}...")
    code_hash = (await client.send_code_request(phone)).phone_code_hash

    code = input("Enter the login code you received in Telegram: ").strip()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=code_hash)
    except SessionPasswordNeededError:
        password = input("Enter your Telegram Two-Step Verification (2FA) password: ").strip()
        await client.sign_in(password=password)

    session_string = client.session.save()
    me = await client.get_me()
    print(f"\n✅ Authorization successful for: {me.first_name} (@{me.username or 'none'}, ID: {me.id})")
    await client.disconnect()

    # Write credentials to .env
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        replaced_keys = set()
        for line in lines:
            if line.startswith("TELEGRAM_API_ID="):
                new_lines.append(f"TELEGRAM_API_ID={api_id}\n")
                replaced_keys.add("TELEGRAM_API_ID")
            elif line.startswith("TELEGRAM_API_HASH="):
                new_lines.append(f"TELEGRAM_API_HASH={api_hash}\n")
                replaced_keys.add("TELEGRAM_API_HASH")
            elif line.startswith("TELEGRAM_SESSION_STRING="):
                new_lines.append(f"TELEGRAM_SESSION_STRING={session_string}\n")
                replaced_keys.add("TELEGRAM_SESSION_STRING")
            elif line.startswith("QUOTEX_VERIFICATION_PROVIDER="):
                new_lines.append("QUOTEX_VERIFICATION_PROVIDER=mtproto\n")
                replaced_keys.add("QUOTEX_VERIFICATION_PROVIDER")
            else:
                new_lines.append(line)

        if "TELEGRAM_API_ID" not in replaced_keys:
            new_lines.append(f"TELEGRAM_API_ID={api_id}\n")
        if "TELEGRAM_API_HASH" not in replaced_keys:
            new_lines.append(f"TELEGRAM_API_HASH={api_hash}\n")
        if "TELEGRAM_SESSION_STRING" not in replaced_keys:
            new_lines.append(f"TELEGRAM_SESSION_STRING={session_string}\n")
        if "QUOTEX_VERIFICATION_PROVIDER" not in replaced_keys:
            new_lines.append("QUOTEX_VERIFICATION_PROVIDER=mtproto\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print(f"\n✅ Credentials written directly to: {os.path.abspath(env_path)}")
    else:
        print("\nSave these lines in your .env file:\n")
        print(f"TELEGRAM_API_ID={api_id}")
        print(f"TELEGRAM_API_HASH={api_hash}")
        print(f"TELEGRAM_SESSION_STRING={session_string}\n")

    print("=" * 60)
    print("SUCCESS! Automated Quotex Partner Bot integration is now configured.")
    print("=" * 60)


def main():
    loop.run_until_complete(run_auth())


if __name__ == "__main__":
    main()
