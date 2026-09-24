"""
Get your Telegram channel's numeric chat ID.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import requests
from dotenv import load_dotenv
load_dotenv()

def get_channel_id(bot_token, channel_name):
    """Get channel ID by checking bot's recent updates."""
    print(f"\nChecking bot for channel: {channel_name}")

    # First, make sure bot is admin of the channel
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    try:
        response = requests.get(url, timeout=15)
        data = response.json()

        if not data.get("ok"):
            print(f"Error: {data}")
            return None

        updates = data.get("result", [])
        print(f"Found {len(updates)} updates")

        for update in updates:
            msg = update.get("channel_post") or update.get("message") or update.get("my_chat_member")
            if msg:
                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                chat_title = chat.get("title", "Unknown")
                chat_type = chat.get("type", "Unknown")

                if chat_type == "channel" or str(chat_id).startswith("-100"):
                    print(f"\n  FOUND CHANNEL:")
                    print(f"  Title: {chat_title}")
                    print(f"  Chat ID: {chat_id}")
                    print(f"  Type: {chat_type}")
                    return chat_id

        print("\nNo channel posts found in recent updates.")
        print("Make sure:")
        print("  1. Bot is added as admin to the channel")
        print("  2. Send a test message in the channel")
        print("  3. Run this script again")
        return None

    except requests.exceptions.ConnectTimeout:
        print("Network timeout - can't reach Telegram API from this machine")
        print("Try from a different network or use a VPN")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# Check Premium bot
premium_token = os.getenv("TELEGRAM_BOT_TOKEN_PREMIUM", "")
if premium_token and premium_token != "create_this_bot":
    channel_id = get_channel_id(premium_token, "Premium")
    if channel_id:
        print(f"\nAdd this to .env:")
        print(f"TELEGRAM_CHANNEL_PREMIUM={channel_id}")

# Check VIP bot (if exists)
vip_token = os.getenv("TELEGRAM_BOT_TOKEN_VIP", "")
if vip_token and vip_token != "create_this_bot":
    channel_id = get_channel_id(vip_token, "VIP")
    if channel_id:
        print(f"\nAdd this to .env:")
        print(f"TELEGRAM_CHANNEL_VIP={channel_id}")
