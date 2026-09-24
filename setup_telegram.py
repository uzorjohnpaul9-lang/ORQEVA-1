"""
Telegram Bot Setup Helper
Run this and follow the prompts to set up your 3 bots.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

ENV_FILE = Path(__file__).parent / ".env"

def update_env(key, value):
    """Update a key in .env file."""
    content = ENV_FILE.read_text()
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    ENV_FILE.write_text("\n".join(lines))

def setup_bot(tier, env_key):
    """Setup a single bot."""
    print(f"\n{'='*50}")
    print(f"SETUP: {tier.upper()} TIER BOT")
    print(f"{'='*50}")
    
    print(f"\n1. Open Telegram and search for @BotFather")
    print(f"2. Send this message to BotFather:")
    print(f"\n   /newbot\n")
    
    name = input(f"3. What did you name the bot? (e.g., 'AI Trading Free'): ").strip()
    username = input(f"4. What username did you give it? (e.g., 'MyTradingFreeBot'): ").strip()
    
    print(f"\n5. BotFather should have given you a token.")
    print(f"   It looks like: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ")
    
    token = input(f"\n6. Paste the token here: ").strip()
    
    if token:
        update_env(env_key, token)
        print(f"\n   [OK] Token saved to .env")
        return True
    else:
        print(f"\n   [SKIP] No token provided")
        return False

def get_chat_id():
    """Get user's chat ID."""
    print(f"\n{'='*50}")
    print(f"GET YOUR CHAT ID")
    print(f"{'='*50}")
    
    print(f"\n1. Open Telegram and search for @userinfobot")
    print(f"2. Send /start")
    print(f"3. It will show your Chat ID (a number)")
    
    chat_id = input(f"\n4. Paste your Chat ID here: ").strip()
    
    if chat_id:
        for key in ["TELEGRAM_CHAT_IDS_FREE", "TELEGRAM_CHAT_IDS_PREMIUM", "TELEGRAM_CHAT_IDS_VIP"]:
            update_env(key, chat_id)
        print(f"\n   [OK] Chat ID saved to all tiers")
        return True
    return False

def main():
    print("=" * 50)
    print("TELEGRAM BOT SETUP")
    print("=" * 50)
    print("\nThis will help you create 3 Telegram bots:")
    print("  - Free Tier (3 signals/day)")
    print("  - Premium Tier (15 signals/day)")  
    print("  - VIP Tier (unlimited signals)")
    
    input("\nPress Enter to start...")
    
    # Setup Free Bot
    setup_bot("Free", "TELEGRAM_BOT_TOKEN_FREE")
    
    # Setup Premium Bot
    input("\nPress Enter to setup Premium bot...")
    setup_bot("Premium", "TELEGRAM_BOT_TOKEN_PREMIUM")
    
    # Setup VIP Bot
    input("\nPress Enter to setup VIP bot...")
    setup_bot("VIP", "TELEGRAM_BOT_TOKEN_VIP")
    
    # Get Chat ID
    input("\nPress Enter to get your Chat ID...")
    get_chat_id()
    
    # Summary
    print(f"\n{'='*50}")
    print("SETUP COMPLETE")
    print(f"{'='*50}")
    
    print("\nYour bots:")
    for tier, key in [("Free", "FREE"), ("Premium", "PREMIUM"), ("VIP", "VIP")]:
        token = os.getenv(f"TELEGRAM_BOT_TOKEN_{key}", "")
        status = "OK" if token and token != "create_this_bot" else "NOT SET"
        print(f"  {tier}: {status}")
    
    print("\nTo test: python test_notifications.py")

if __name__ == "__main__":
    main()
