import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import requests
from dotenv import load_dotenv
load_dotenv()

WALLET = "TVTd5E174wygdqAUBYddFWgViLTQJRKytf"
ADMIN = "@Johnpaulmuna_83"
BINANCE_REF = "https://www.binance.com/activity/referral-entry/CPA?ref=CPA_00N4AMKT4D"

channels = {
    "Free": {
        "token_env": "TELEGRAM_BOT_TOKEN_FREE",
        "channel_env": "TELEGRAM_CHANNEL_FREE",
        "desc": (
            "AI Trading Signals - FREE\n\n"
            "Get 3 free stock signals daily.\n"
            "Trade stocks using our Binance link.\n\n"
            "Premium ($49/mo): 15 signals + Forex\n"
            "VIP ($199/mo): Unlimited + Crypto + Auto-Trade\n\n"
            f"DM {ADMIN} to upgrade."
        ),
    },
    "Premium": {
        "token_env": "TELEGRAM_BOT_TOKEN_PREMIUM",
        "channel_env": "TELEGRAM_CHANNEL_PREMIUM",
        "desc": (
            "AI Trading Signals - PREMIUM\n\n"
            "15 signals/day: Stocks + Forex.\n"
            "Entry/exit prices included.\n\n"
            f"Price: $49/month\n"
            f"Payment: USDT (TRC20)\n"
            f"Wallet: {WALLET}\n\n"
            f"Upgrade to VIP ($199/mo) for:\n"
            f"- Crypto signals (BTC, ETH, SOL, etc.)\n"
            f"- Auto-trade option\n"
            f"- Unlimited signals\n\n"
            f"DM {ADMIN} for VIP access."
        ),
    },
    "VIP": {
        "token_env": "TELEGRAM_BOT_TOKEN_VIP",
        "channel_env": "TELEGRAM_CHANNEL_VIP",
        "desc": (
            "AI Trading Signals - VIP\n\n"
            "Everything included:\n"
            "- Unlimited Stocks + Forex + Crypto\n"
            "- Auto-trade option (opt-in)\n"
            "- AI portfolio management\n"
            "- Priority execution\n\n"
            f"Price: $199/month\n"
            f"Payment: USDT (TRC20)\n"
            f"Wallet: {WALLET}\n\n"
            f"Contact {ADMIN} to enable auto-trade."
        ),
    },
}

def update_channel(tier, config):
    token = os.getenv(config["token_env"], "")
    channel_id = os.getenv(config["channel_env"], "")
    if not token or token == "create_this_bot":
        print(f"  {tier}: No bot token")
        return False
    if not channel_id:
        print(f"  {tier}: No channel ID")
        return False
    url = f"https://api.telegram.org/bot{token}/setChatDescription"
    try:
        r = requests.post(url, json={"chat_id": channel_id, "description": config["desc"]}, timeout=15)
        result = r.json()
        if result.get("ok"):
            print(f"  {tier}: Updated!")
            return True
        else:
            print(f"  {tier}: Error - {result.get('description', 'Unknown')}")
            return False
    except Exception as e:
        print(f"  {tier}: Error - {e}")
        return False

print("Updating channel descriptions...")
for tier, config in channels.items():
    print(f"\n{tier}:")
    update_channel(tier, config)
print("\nDone!")
