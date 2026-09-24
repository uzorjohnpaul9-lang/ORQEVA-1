import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from notifications.channel_notifier import ChannelNotifier
from dotenv import load_dotenv
load_dotenv()

notifier = ChannelNotifier()

signal = {
    "direction": "SELL",
    "symbol": "META",
    "price": 580.25,
    "confidence": 0.94,
    "reason": "Overbought RSI + resistance rejection"
}

print("Sending test signal to VIP channel...")
notifier.send_signal(signal, target_tiers=["vip"])
print("Done! Check your VIP Telegram channel.")
