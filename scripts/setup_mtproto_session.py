#!/usr/bin/env python3
"""Interactive setup script for generating Telethon MTProto StringSession.

Run this script once locally to authenticate your affiliate Telegram account
which has access to @QuotexPartnerBot.

Security notice:
- The resulting session string will be written to .env as TELEGRAM_SESSION_STRING.
- Never commit .env or share this session string.
"""

import os
import sys
from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def main():
    print("=" * 60)
    print("PRIME SCALPERS • MTPROTO SESSION SETUP WIZARD")
    print("=" * 60)
    print("This wizard generates a secure Telethon StringSession to enable")
    print("automated queries to @QuotexPartnerBot.\n")
    print("Get your API credentials from: https://my.telegram.org (under 'API development tools')\n")

    api_id_str = input("Enter your Telegram API_ID: ").strip()
    if not api_id_str.isdigit():
        print("❌ Invalid API ID. Must be numeric.")
        sys.exit(1)
    api_id = int(api_id_str)

    api_hash = input("Enter your Telegram API_HASH: ").strip()
    if not api_hash:
        print("❌ Invalid API HASH.")
        sys.exit(1)

    print("\nConnecting to Telegram to authorize your affiliate account...")
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()
        me = client.get_me()
        print(f"\n✅ Authorization successful for: {me.first_name} (@{me.username or 'none'})")

    print("\nSession string generated successfully!")

    # Offer to update .env
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
            else:
                new_lines.append(line)

        if "TELEGRAM_API_ID" not in replaced_keys:
            new_lines.append(f"TELEGRAM_API_ID={api_id}\n")
        if "TELEGRAM_API_HASH" not in replaced_keys:
            new_lines.append(f"TELEGRAM_API_HASH={api_hash}\n")
        if "TELEGRAM_SESSION_STRING" not in replaced_keys:
            new_lines.append(f"TELEGRAM_SESSION_STRING={session_string}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print(f"✅ Credentials written directly to: {os.path.abspath(env_path)}")
    else:
        print("\nSave the following lines into your .env file:\n")
        print(f"TELEGRAM_API_ID={api_id}")
        print(f"TELEGRAM_API_HASH={api_hash}")
        print(f"TELEGRAM_SESSION_STRING={session_string}\n")

    print("Setup complete! Your bot can now query @QuotexPartnerBot automatically.")


if __name__ == "__main__":
    main()
