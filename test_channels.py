"""
Test the channel notification system.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from notifications.channel_notifier import ChannelNotifier, TIER_CONFIG
from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 60)
print("CHANNEL NOTIFICATION SYSTEM")
print("=" * 60)

notifier = ChannelNotifier()

# Show tier config
print("\n--- Tier Configuration ---")
for tier, config in TIER_CONFIG.items():
    signals = "Unlimited" if config["max_signals_per_day"] == -1 else config["max_signals_per_day"]
    print(f"  {config['name']:10s} | ${config['price']:3d}/mo | {signals} signals/day")

# Show channel configuration
print("\n--- Channel Configuration ---")
for tier in TIER_CONFIG:
    channel = os.getenv(TIER_CONFIG[tier]["channel_env"], "NOT SET")
    bot_token = os.getenv(TIER_CONFIG[tier]["bot_token_env"], "NOT SET")
    bot_status = "OK" if bot_token and bot_token != "create_this_bot" else "NOT SET"
    print(f"  {tier:10s}: Channel={channel} | Bot={bot_status}")

# Test sending a signal
print("\n--- Test Signal ---")
test_signal = {
    "direction": "BUY",
    "symbol": "AAPL",
    "price": 195.50,
    "confidence": 0.85,
    "reason": "Strong momentum + RSI oversold"
}

print("Sending test signal to Free channel...")
notifier.send_signal(test_signal, target_tiers=["free"])

# Show usage
print("\n--- Usage Stats ---")
stats = notifier.get_usage_stats()
for tier, data in stats.items():
    max_sig = "Unlimited" if data["max_signals"] == -1 else data["max_signals"]
    print(f"  {tier:10s}: {data['signals_today']}/{max_sig} signals used today")

print("\n" + "=" * 60)
print("Check your Telegram channels for the test signal!")
print("=" * 60)
