import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from notifications.channel_notifier import ChannelNotifier
from dotenv import load_dotenv
load_dotenv()

notifier = ChannelNotifier()

signal = {
    "direction": "BUY",
    "symbol": "NVDA",
    "price": 120.50,
    "confidence": 0.92,
    "reason": "AI sector breakout + earnings beat"
}

print("Sending updated signal to Free channel...")
notifier.send_signal(signal, target_tiers=["free"])
print("Done! Check your Telegram.")
