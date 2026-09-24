"""
Test the tiered notification system.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from notifications.tiered_notifier import TieredNotifier, TIER_CONFIG
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("TIERED NOTIFICATION SYSTEM")
print("=" * 60)

notifier = TieredNotifier()

# Show tier config
print("\n--- Tier Configuration ---")
for tier, config in TIER_CONFIG.items():
    signals = "Unlimited" if config["max_signals_per_day"] == -1 else config["max_signals_per_day"]
    trades = "Unlimited" if config["max_trades_per_day"] == -1 else config["max_trades_per_day"]
    print(f"  {config['name']:10s} | ${config['price']:3d}/mo | {signals} signals | {trades} trades/day")

# Show subscriber counts
print("\n--- Current Subscribers ---")
for tier in TIER_CONFIG:
    count = len(notifier.subscribers.get(tier, []))
    print(f"  {tier:10s}: {count} subscribers")

# Show usage
print("\n--- Usage Stats ---")
stats = notifier.get_usage_stats()
for tier, data in stats.items():
    print(f"  {tier:10s}: {data['signals_today']}/{data['max_signals']} signals used today")

# Check which bots are configured
print("\n--- Bot Configuration ---")
import os
for tier, config in TIER_CONFIG.items():
    token = os.getenv(config["bot_token_env"], "")
    status = "CONFIGURED" if token and token != "create_this_bot" else "NOT SET"
    print(f"  {tier:10s}: {status}")

print("\n" + "=" * 60)
print("To configure bots, update .env file with your Telegram bot tokens")
print("=" * 60)
